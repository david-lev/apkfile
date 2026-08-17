"""The `.apkv` bundle format: a base apk + splits + a JSON manifest, optionally password-encrypted.

See the [APKv spec](https://github.com/vinstall/apkv-spec) (v2, stable, public domain). VInstall
(https://github.com/vinstall/VInstall) is the reference implementation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger

from ._bundle import _BaseBundle
from .exceptions import EncryptedBundleError, InvalidBundleError

__all__ = ["ApkvFile"]

# APKv spec §6: encryption is detected via this sentinel entry, never the manifest's own
# `encrypted` field (which a corrupt/adversarial archive could misreport).
_ENCRYPTED_SENTINEL = ".apkv_enc"

# APKv spec §5.1/§5.2.
_PBKDF2_ITERATIONS = 120_000
_KEY_LENGTH = 32  # 256 bits
_SALT_LENGTH = 16
_IV_LENGTH = 16

# Common split-apk filename prefixes (bundletool/APKM/XAPK/AAB all use one of these), used as a
# last-resort heuristic to guess which `.apkv` split is the base — the spec doesn't designate one.
_SPLIT_PREFIXES = ("split_config.", "config.", "split.")


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _decrypt(blob: bytes, password: str, *, path: Path) -> bytes:
    """Decrypt a `[salt(16)][iv(16)][AES-256-CBC/PKCS5 ciphertext]` blob (APKv spec §5.2)."""
    if len(blob) < _SALT_LENGTH + _IV_LENGTH:
        raise EncryptedBundleError(f"{path!r} has a truncated encrypted entry")
    salt = blob[:_SALT_LENGTH]
    iv = blob[_SALT_LENGTH : _SALT_LENGTH + _IV_LENGTH]
    ciphertext = blob[_SALT_LENGTH + _IV_LENGTH :]
    key = _derive_key(password, salt)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    try:
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as e:
        # AES-CBC has no built-in integrity check (spec §5.4/§10.5) — a bad password almost always
        # (but isn't guaranteed to) surface as a PKCS#5 padding error at this point.
        raise EncryptedBundleError(
            f"Incorrect password for {path!r} (or a corrupt archive)"
        ) from e


class ApkvFile(_BaseBundle):
    """
    A [VInstall](https://github.com/vinstall/VInstall) `.apkv` bundle: a base apk + splits +
    `manifest.json`, optionally password-encrypted.

    See the [APKv spec](https://github.com/vinstall/apkv-spec) for the full format.

    >>> apkv = ApkvFile("/home/user/chrome.apkv")
    >>> for split in apkv.splits:
    ...     print(split.split_name)
    >>> apkv.install(upgrade=True)

    >>> secret = ApkvFile("/home/user/backup.apkv", password="hunter2")

    Attributes:
        base: The base apk.
        splits: The split apks.
        app_name: The app's display name (the manifest's `label` field).
        apkv_version: The version of the `.apkv` format itself (the manifest's `formatVersion`).
        exported_at: When the archive was exported, if the manifest records it.

    See [`ApkFile`][apkfile.ApkFile] for the rest of the shared attributes (`package_name`, `version_code`, ...).
    """

    _EXTRA_FIELDS = ("app_name", "apkv_version", "exported_at")
    app_name: str
    apkv_version: int
    exported_at: datetime | None

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        password: str | None = None,
        skip_broken_splits: bool = False,
        verify_checksums: bool = False,
    ) -> None:
        """
        Args:
            path: Path to the `.apkv` file.
            password: The archive's password, if it's encrypted (see `.apkv_enc`, spec §6).
            skip_broken_splits: If `True`, broken split apks are skipped instead of raising.
            verify_checksums: If `True`, verify each split's bytes against the manifest's `checksums`
                map (if present), raising `InvalidBundleError` naming any mismatch (spec §4.1.2).

        Raises:
            FileNotFoundError: If the file does not exist.
            InvalidBundleError: If the file is not a valid `.apkv` bundle, or a checksum mismatches.
            EncryptedBundleError: If the archive is encrypted and `password` is missing or wrong.
        """
        self.path = Path(path)
        logger.debug("Loading .apkv from {}", self.path)
        self._skip_broken_splits = skip_broken_splits
        self._eager: dict[str, Any] = {}
        self._password: str | None = None
        self._outer_zip = zipfile.ZipFile(self.path)
        self._encrypted = _ENCRYPTED_SENTINEL in self._outer_zip.namelist()
        if self._encrypted:
            logger.debug("{} is password-encrypted", self.path)

        manifest = (
            self._read_encrypted_manifest(password)
            if self._encrypted
            else self._read_plain_manifest()
        )
        self._manifest = manifest

        try:
            self.app_name = str(manifest["label"])
            self.apkv_version = int(manifest["formatVersion"])
            self.package_name = str(manifest["packageName"])
            self.version_code = int(manifest["versionCode"])
            splits: list[str] = list(manifest["splits"])
        except KeyError as e:
            raise InvalidBundleError(
                f"{self.path!r} manifest is missing required key {e.args[0]!r}"
            ) from e
        if not splits:
            raise InvalidBundleError(f"{self.path!r} manifest declares no splits")

        if manifest.get("versionName") is not None:
            self._eager["version_name"] = str(manifest["versionName"])
        if manifest.get("minSdkVersion") is not None:
            self._eager["min_sdk_version"] = int(manifest["minSdkVersion"])
        if manifest.get("targetSdkVersion") is not None:
            self._eager["target_sdk_version"] = int(manifest["targetSdkVersion"])

        exported_at = manifest.get("exportedAt")
        self.exported_at = (
            datetime.fromtimestamp(exported_at / 1000, tz=timezone.utc)
            if exported_at is not None
            else None
        )

        self._base_name = self._resolve_base_name(splits)
        self._icon_name = "icon.webp"

        if verify_checksums:
            logger.debug("Verifying checksums for {} split(s)", len(splits))
            self._verify_checksums(manifest.get("checksums") or {}, splits)

    def _read_plain_manifest(self) -> dict[str, Any]:
        try:
            with self._outer_zip.open("manifest.json") as f:
                manifest = json.load(f)
        except KeyError as e:
            raise InvalidBundleError(f"{self.path!r} has no manifest.json") from e
        except json.JSONDecodeError as e:
            raise InvalidBundleError(
                f"{self.path!r} has an invalid manifest.json"
            ) from e
        if manifest.get("format") != "apkv":
            raise InvalidBundleError(f"{self.path!r} is not a valid .apkv archive")
        self._zip = self._outer_zip
        return manifest

    def _read_encrypted_manifest(self, password: str | None) -> dict[str, Any]:
        if password is None:
            raise EncryptedBundleError(
                f"{self.path!r} is password-encrypted; pass password=..."
            )
        self._password = password
        logger.debug("Decrypting manifest.enc for {}", self.path)
        try:
            manifest_blob = self._outer_zip.read("manifest.enc")
        except KeyError as e:
            raise InvalidBundleError(f"{self.path!r} has no manifest.enc") from e
        # APKv spec §7: verifying the password means checking that decrypting `manifest.enc`
        # succeeds and yields JSON with `format == "apkv"` — cheaper than decrypting `payload.enc`.
        plaintext = _decrypt(manifest_blob, password, path=self.path)
        try:
            manifest = json.loads(plaintext)
        except json.JSONDecodeError as e:
            raise EncryptedBundleError(
                f"Incorrect password for {self.path!r} (or a corrupt archive)"
            ) from e
        if manifest.get("format") != "apkv":
            raise EncryptedBundleError(
                f"Incorrect password for {self.path!r} (or a corrupt archive)"
            )

        logger.debug("Decrypting payload.enc for {}", self.path)
        try:
            payload_blob = self._outer_zip.read("payload.enc")
        except KeyError as e:
            raise InvalidBundleError(f"{self.path!r} has no payload.enc") from e
        payload = _decrypt(payload_blob, password, path=self.path)
        # The decrypted payload is itself a zip of the raw `.apk` splits (spec §5.5) — independent
        # of the on-disk file, so it survives `rename()` without needing to be redecrypted.
        self._zip = zipfile.ZipFile(io.BytesIO(payload))
        return manifest

    @staticmethod
    def _resolve_base_name(splits: list[str]) -> str:
        """Best-effort guess at which split is the base apk — the spec doesn't designate one."""
        if "base.apk" in splits:
            return "base.apk"
        if len(splits) == 1:
            return splits[0]
        for name in splits:
            if not any(name.startswith(prefix) for prefix in _SPLIT_PREFIXES):
                return name
        return splits[0]

    def _verify_checksums(self, checksums: dict[str, Any], splits: list[str]) -> None:
        mismatches: list[str] = []
        for name in splits:
            expected = checksums.get(name)
            if not expected:
                continue
            try:
                data = self._zip.read(name)
            except KeyError:
                continue  # a missing split entirely surfaces later, from `.base`/`.splits`
            actual = f"sha256:{hashlib.sha256(data).hexdigest()}"
            if actual != expected:
                mismatches.append(name)
        if mismatches:
            raise InvalidBundleError(
                f"{self.path!r} failed checksum verification for: {', '.join(mismatches)}"
            )

    @property
    def encrypted(self) -> bool:
        """Whether this archive is password-encrypted."""
        return self._encrypted

    @cached_property
    def icon_bytes(self) -> bytes | None:
        """The bundle's own icon (as shipped by the tool that created the archive), if any."""
        if not self._encrypted:
            try:
                return self._zip.read(self._icon_name)
            except KeyError:
                return None
        try:
            blob = self._outer_zip.read("icon.enc")
        except KeyError:
            return None
        assert (
            self._password is not None
        )  # required to get this far (see _read_encrypted_manifest)
        return _decrypt(blob, self._password, path=self.path)

    def _close_for_rename(self) -> None:
        self._outer_zip.close()

    def _reopen_after_rename(self) -> None:
        self._outer_zip = zipfile.ZipFile(self.path)
        if not self._encrypted:
            self._zip = self._outer_zip
        # else: `self._zip` is the in-memory decrypted payload, unrelated to the on-disk path.
