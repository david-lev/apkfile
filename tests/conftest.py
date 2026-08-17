from __future__ import annotations

import io
import json
import os
import subprocess
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DATA_DIR = Path(__file__).parent / "data" / "apk"
POLITEDROID_PATH = str(DATA_DIR / "politedroid.apk")
TEST_DEBUG_PATH = str(DATA_DIR / "test-debug.apk")


@pytest.fixture
def politedroid_path() -> str:
    """A small real apk with permissions, a single locale, and 4 icon densities."""
    return POLITEDROID_PATH


@pytest.fixture
def test_debug_path() -> str:
    """A minimal real apk: no permissions, no native code, no icon."""
    return TEST_DEBUG_PATH


@pytest.fixture
def politedroid_bytes() -> bytes:
    return Path(POLITEDROID_PATH).read_bytes()


@pytest.fixture
def test_debug_bytes() -> bytes:
    return Path(TEST_DEBUG_PATH).read_bytes()


@pytest.fixture
def apk_with_native_libs(tmp_path: Path, politedroid_bytes: bytes) -> str:
    """A copy of politedroid.apk with fake native library entries injected under lib/."""
    src = zipfile.ZipFile(io.BytesIO(politedroid_bytes))
    out_path = tmp_path / "with-libs.apk"
    with zipfile.ZipFile(out_path, "w") as out:
        for item in src.infolist():
            out.writestr(item, src.read(item.filename))
        out.writestr("lib/arm64-v8a/libfoo.so", b"fake")
        out.writestr("lib/armeabi-v7a/libfoo.so", b"fake")
    return str(out_path)


@pytest.fixture
def make_apkm(
    tmp_path: Path, politedroid_bytes: bytes, test_debug_bytes: bytes
) -> Callable[..., str]:
    def _make(
        *, with_split: bool = True, extra_info: dict[str, Any] | None = None
    ) -> str:
        info = {
            "app_name": "Polite Droid",
            "apkm_version": 2,
            "pname": "com.politedroid",
            "versioncode": 4,
            "min_api": 3,
            "release_version": "1.3",
        }
        info.update(extra_info or {})
        path = tmp_path / "sample.apkm"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("info.json", json.dumps(info))
            z.writestr("base.apk", politedroid_bytes)
            if with_split:
                z.writestr("split_config.arm64_v8a.apk", test_debug_bytes)
            z.writestr("icon.png", b"fake-icon")
        return str(path)

    return _make


@pytest.fixture
def make_xapk(
    tmp_path: Path, politedroid_bytes: bytes, test_debug_bytes: bytes
) -> Callable[..., str]:
    def _make(
        *,
        with_split: bool = True,
        with_obb: bool = False,
        extra_info: dict[str, Any] | None = None,
    ) -> str:
        info = {
            "name": "Polite Droid",
            "xapk_version": 2,
            "package_name": "com.politedroid",
            "version_code": 4,
            "min_sdk_version": 3,
            "version_name": "1.3",
        }
        if with_obb:
            info["expansions"] = [
                {
                    "file": "Android/obb/com.politedroid/main.4.com.politedroid.obb",
                    "install_location": "EXTERNAL_STORAGE",
                    "install_path": "Android/obb/com.politedroid/main.4.com.politedroid.obb",
                },
                {
                    "file": "Android/obb/com.politedroid/patch.4.com.politedroid.obb",
                    "install_location": "EXTERNAL_STORAGE",
                    "install_path": "Android/obb/com.politedroid/patch.4.com.politedroid.obb",
                },
                # declared but never actually written into the zip below.
                {"file": "Android/obb/com.politedroid/missing.obb"},
            ]
        info.update(extra_info or {})
        path = tmp_path / "sample.xapk"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("manifest.json", json.dumps(info))
            z.writestr("com.politedroid.apk", politedroid_bytes)
            if with_split:
                z.writestr("config.arm64_v8a.apk", test_debug_bytes)
            if with_obb:
                z.writestr(
                    "Android/obb/com.politedroid/main.4.com.politedroid.obb",
                    b"main-obb-bytes",
                )
                z.writestr(
                    "Android/obb/com.politedroid/patch.4.com.politedroid.obb",
                    b"patch-obb-bytes",
                )
            z.writestr("icon.png", b"fake-icon")
        return str(path)

    return _make


@pytest.fixture
def make_apks(
    tmp_path: Path, politedroid_bytes: bytes, test_debug_bytes: bytes
) -> Callable[..., str]:
    def _make(*, meta_version: int = 2, with_split: bool = True) -> str:
        info: dict[str, Any] = {
            "package": "com.politedroid",
            "label": "Polite Droid",
            "version_code": 4,
        }
        manifest_name = "meta.sai_v1.json"
        if meta_version == 2:
            info["meta_version"] = 2
            manifest_name = "meta.sai_v2.json"
        path = tmp_path / f"sample_v{meta_version}.apks"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr(manifest_name, json.dumps(info))
            z.writestr("base.apk", politedroid_bytes)
            if with_split:
                z.writestr("split_config.arm64_v8a.apk", test_debug_bytes)
            z.writestr("icon.png", b"fake-icon")
        return str(path)

    return _make


def _apkv_encrypt(data: bytes, password: str) -> bytes:
    """[salt(16)][iv(16)][AES-256-CBC/PKCS5 ciphertext] — the APKv spec §5.2 blob layout."""
    salt = os.urandom(16)
    iv = os.urandom(16)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=120_000
    ).derive(password.encode("utf-8"))
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(data) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return salt + iv + encryptor.update(padded) + encryptor.finalize()


@pytest.fixture
def apkv_encrypt() -> Callable[[bytes, str], bytes]:
    """Independently re-encrypts APKv spec §5.2 blobs, for tests that build an archive by hand."""
    return _apkv_encrypt


@pytest.fixture
def make_apkv(
    tmp_path: Path, politedroid_bytes: bytes, test_debug_bytes: bytes
) -> Callable[..., str]:
    def _make(
        *,
        with_split: bool = True,
        encrypted: bool = False,
        password: str = "hunter2",
        extra_manifest: dict[str, Any] | None = None,
    ) -> str:
        splits_data = {"base.apk": politedroid_bytes}
        if with_split:
            splits_data["split_config.arm64_v8a.apk"] = test_debug_bytes
        manifest: dict[str, Any] = {
            "format": "apkv",
            "formatVersion": 2,
            "packageName": "com.politedroid",
            "versionName": "1.3",
            "versionCode": 4,
            "label": "Polite Droid",
            "isSplit": with_split,
            "splits": list(splits_data),
            "encrypted": encrypted,
            "hasIcon": False,
            "exportedAt": 1743667200000,
            "minSdkVersion": 3,
            "targetSdkVersion": 29,
        }
        manifest.update(extra_manifest or {})
        path = tmp_path / ("sample_enc.apkv" if encrypted else "sample.apkv")

        with zipfile.ZipFile(path, "w") as z:
            if not encrypted:
                z.writestr("manifest.json", json.dumps(manifest))
                for name, data in splits_data.items():
                    z.writestr(name, data)
            else:
                z.writestr(".apkv_enc", b"")
                z.writestr(
                    "header.json",
                    json.dumps(
                        {
                            "packageName": manifest["packageName"],
                            "versionName": manifest["versionName"],
                            "label": manifest["label"],
                            "encrypted": True,
                            "hasIcon": False,
                        }
                    ),
                )
                z.writestr(
                    "manifest.enc",
                    _apkv_encrypt(json.dumps(manifest).encode(), password),
                )
                payload_buf = io.BytesIO()
                with zipfile.ZipFile(payload_buf, "w") as pz:
                    for name, data in splits_data.items():
                        pz.writestr(name, data)
                z.writestr(
                    "payload.enc", _apkv_encrypt(payload_buf.getvalue(), password)
                )
        return str(path)

    return _make


class FakeAdb:
    """Records every ``subprocess.run`` call and dispatches canned responses to them, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._handlers: list[tuple[Callable[[tuple[str, ...]], bool], Any]] = []

    def on(
        self,
        predicate: Callable[[tuple[str, ...]], bool],
        response: str | BaseException,
    ) -> None:
        self._handlers.append((predicate, response))

    def __call__(
        self,
        args: Any,
        capture_output: bool = True,
        text: bool = True,
        check: bool = True,
    ) -> Any:
        args = tuple(args)
        self.calls.append(args)
        for predicate, response in self._handlers:
            if predicate(args):
                if isinstance(response, BaseException):
                    raise response
                return subprocess.CompletedProcess(args, 0, stdout=response, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


@pytest.fixture
def fake_adb(mocker) -> FakeAdb:
    """A fake ``adb`` for ``install_apks`` tests: no real device/binary needed."""
    adb = FakeAdb()
    mocker.patch("shutil.which", return_value="/usr/bin/adb")
    mocker.patch("subprocess.run", side_effect=adb)
    return adb
