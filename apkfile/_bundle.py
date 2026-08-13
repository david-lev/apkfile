"""Bundle archive formats: ``.apkm``, ``.xapk``, ``.apks`` — each a zip of a base apk + splits + a JSON manifest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import Any

from ._apk import ApkFile, _jsonable
from ._resources import ScreenSize
from ._security import SecurityInfo
from ._signing import SigningInfo
from ._size import DexInfo, SizeBreakdown, sum_dex_infos, sum_size_breakdowns
from .abi import Abi
from .enums import FormFactor, InstallLocation
from .exceptions import ApkFileError, InvalidApkError, InvalidBundleError

__all__ = ["ApkmFile", "ApksFile", "XapkFile"]

_HASH_CHUNK_SIZE = 1024 * 1024

# attr name -> (json key, type, required)
_ManifestAttr = tuple[str, type, bool]


class _BaseBundle:
    """Shared implementation for ``.apkm``/``.xapk``/``.apks``."""

    path: Path
    package_name: str
    version_code: int
    _base_name: str
    _icon_name: str
    _BASE_FIELDS: tuple[str, ...] = (
        "path",
        "package_name",
        "version_code",
        "version_name",
        "min_sdk_version",
        "target_sdk_version",
        "max_sdk_version",
        "install_location",
        "labels",
        "permissions",
        "libraries",
        "features",
        "launchable_activity",
        "supported_screens",
        "supports_any_density",
        "langs",
        "densities",
        "abis",
        "form_factors",
        "size",
        "md5",
        "sha256",
        "signing",
        "security",
        "size_breakdown",
        "dex_info",
    )
    _EXTRA_FIELDS: tuple[str, ...] = ()
    _FALLBACK_ATTRS: frozenset[str] = frozenset(
        {"version_name", "min_sdk_version", "target_sdk_version"}
    )

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        manifest_name: str,
        base_apk_name: str,
        icon_name: str,
        manifest_attrs: Mapping[str, _ManifestAttr],
        skip_broken_splits: bool = False,
    ) -> None:
        self.path = Path(path)
        self._zip = zipfile.ZipFile(self.path)
        try:
            with self._zip.open(manifest_name) as f:
                info = json.load(f)
        except KeyError as e:
            raise InvalidBundleError(
                f"{self.path!r} has no {manifest_name!r} manifest"
            ) from e
        except json.JSONDecodeError as e:
            raise InvalidBundleError(
                f"{self.path!r} has an invalid {manifest_name!r} manifest"
            ) from e

        def _coerce(typ: type, value: Any, *, key: str) -> Any:
            try:
                return typ(value)
            except (ValueError, TypeError) as e:
                raise InvalidBundleError(
                    f"{self.path!r} manifest key {key!r} is {value!r}, not a valid {typ.__name__}"
                ) from e

        # `version_name`/`min_sdk_version`/`target_sdk_version` fall back to the base apk's own
        # parsed value when the manifest doesn't carry them (see the cached_properties below),
        # so they're stashed in `_eager` instead of being set as plain (possibly-`None`) attrs.
        self._eager: dict[str, Any] = {}
        for attr, (key, typ, required) in manifest_attrs.items():
            has_value = key in info and info[key] is not None
            if attr in self._FALLBACK_ATTRS:
                if has_value:
                    self._eager[attr] = _coerce(typ, info[key], key=key)
                elif required:
                    raise InvalidBundleError(
                        f"{self.path!r} manifest is missing required key {key!r}"
                    )
            elif has_value:
                setattr(self, attr, _coerce(typ, info[key], key=key))
            elif required:
                raise InvalidBundleError(
                    f"{self.path!r} manifest is missing required key {key!r}"
                )
            else:
                setattr(self, attr, None)

        try:
            self._base_name = base_apk_name.format(**info)
            self._icon_name = icon_name.format(**info)
        except KeyError as e:
            raise InvalidBundleError(
                f"{self.path!r} manifest is missing key {e.args[0]!r}"
            ) from e

        self._skip_broken_splits = skip_broken_splits

    # -- base / splits, parsed lazily straight from the zip's bytes (no disk extraction) -----

    @cached_property
    def base(self) -> ApkFile:
        try:
            data = self._zip.read(self._base_name)
        except KeyError as e:
            raise InvalidBundleError(
                f"{self.path!r} has no base apk {self._base_name!r}"
            ) from e
        return ApkFile._from_bytes(data, name=PurePosixPath(self._base_name).name)

    @cached_property
    def splits(self) -> tuple[ApkFile, ...]:
        names = [
            n
            for n in self._zip.namelist()
            if n.endswith(".apk") and n != self._base_name
        ]
        splits: list[ApkFile] = []
        for name in names:
            try:
                splits.append(
                    ApkFile._from_bytes(
                        self._zip.read(name), name=PurePosixPath(name).name
                    )
                )
            except InvalidApkError:
                if not self._skip_broken_splits:
                    raise
        return tuple(splits)

    @cached_property
    def icon_bytes(self) -> bytes | None:
        """The bundle's own icon (as shipped by the tool that created the archive), if any."""
        try:
            return self._zip.read(self._icon_name)
        except KeyError:
            return None

    def extract_icon(self, path: str | os.PathLike[str]) -> None:
        """Write this bundle's icon to ``path``."""
        data = self.icon_bytes
        if data is None:
            raise ApkFileError(f"{self.path!r} has no icon")
        Path(path).write_bytes(data)

    # -- fields derived from base/splits (lazy: only extracted on first access) ---------------

    @cached_property
    def version_name(self) -> str | None:
        return self._eager.get("version_name", None) or self.base.version_name

    @cached_property
    def min_sdk_version(self) -> int | None:
        return self._eager.get("min_sdk_version", None) or self.base.min_sdk_version

    @cached_property
    def target_sdk_version(self) -> int | None:
        return (
            self._eager.get("target_sdk_version", None) or self.base.target_sdk_version
        )

    @cached_property
    def max_sdk_version(self) -> int | None:
        return self.base.max_sdk_version

    @cached_property
    def form_factors(self) -> tuple[FormFactor, ...]:
        return self.base.form_factors

    @cached_property
    def install_location(self) -> InstallLocation:
        return self.base.install_location

    @cached_property
    def supported_screens(self) -> tuple[ScreenSize, ...]:
        return self.base.supported_screens

    @cached_property
    def launchable_activity(self) -> str | None:
        return self.base.launchable_activity

    @cached_property
    def supports_any_density(self) -> bool:
        return self.base.supports_any_density

    @cached_property
    def densities(self) -> tuple[int, ...]:
        return self.base.densities

    @cached_property
    def permissions(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self.base.permissions).union(*(s.permissions for s in self.splits))
            )
        )

    @cached_property
    def features(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.base.features).union(*(s.features for s in self.splits)))
        )

    @cached_property
    def libraries(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.base.libraries).union(*(s.libraries for s in self.splits)))
        )

    @cached_property
    def langs(self) -> tuple[str, ...]:
        return tuple(
            sorted(set(self.base.langs).union(*(s.langs for s in self.splits)))
        )

    @cached_property
    def abis(self) -> tuple[Abi, ...]:
        found = set(self.base.abis).union(*(s.abis for s in self.splits))
        return tuple(sorted(found, key=lambda abi: abi.value))

    @cached_property
    def labels(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for split in self.splits:
            merged.update(split.labels)
        merged.update(self.base.labels)
        return merged

    @cached_property
    def signing(self) -> SigningInfo:
        """The signing scheme(s) and certificate(s) the bundle's base apk was signed with."""
        return self.base.signing

    @cached_property
    def security(self) -> SecurityInfo:
        """The bundle's base apk's manifest security posture."""
        return self.base.security

    @cached_property
    def size_breakdown(self) -> SizeBreakdown:
        """On-disk size, broken down by content category, summed across the base apk + every split."""
        return sum_size_breakdowns(
            (self.base.size_breakdown, *(s.size_breakdown for s in self.splits))
        )

    @cached_property
    def dex_info(self) -> DexInfo:
        """Method/class/string counts summed across the base apk + every split."""
        return sum_dex_infos((self.base.dex_info, *(s.dex_info for s in self.splits)))

    # -- file-ish operations -------------------------------------------------------------------

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    def _hash(self, algorithm: str) -> str:
        digest = hashlib.new(algorithm)
        with self.path.open("rb") as f:
            for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @cached_property
    def md5(self) -> str:
        return self._hash("md5")

    @cached_property
    def sha256(self) -> str:
        return self._hash("sha256")

    def as_zip_file(self) -> zipfile.ZipFile:
        """Get the bundle as a :class:`zipfile.ZipFile`."""
        return zipfile.ZipFile(self.path)

    def extract(
        self, path: str | os.PathLike[str], members: Iterable[str] | None = None
    ) -> None:
        """Extract files from within the archive to a directory."""
        self._zip.extractall(path=path, members=members)

    def rename(self, name: str) -> None:
        """
        Rename the file on disk.

        Args:
            name: The new name of the file. Can contain ``{attr}`` format fields for any str/int attribute.

        Raises:
            TypeError: If a format field isn't a str/int attribute of this instance.
        """
        fields = re.findall(r"{([a-zA-Z_]\w*)}", name)
        values: dict[str, Any] = {}
        for field in fields:
            value = getattr(self, field)
            if not isinstance(value, (str, int)):
                raise TypeError(
                    f"{field!r} is not a str/int attribute of {self.__class__.__name__}"
                )
            values[field] = value
        new_path = self.path.parent / name.format(**values)
        self._zip.close()
        self.path = self.path.rename(new_path)
        self._zip = zipfile.ZipFile(self.path)

    def install(
        self,
        *,
        check: bool = True,
        upgrade: bool = False,
        device_id: str | None = None,
        installer: str | None = None,
        originating_uri: str | None = None,
        adb_path: str | os.PathLike[str] | None = None,
    ) -> None:
        """
        Install this bundle's base + splits on a device using
        `adb <https://developer.android.com/studio/command-line/adb>`_.

        The base and splits are extracted to a temporary directory for the duration of the install, and
        cleaned up automatically afterwards.

        Args:
            check: Check that the app is compatible with the device before installing.
            upgrade: Whether to upgrade the app if it's already installed (``INSTALL_FAILED_ALREADY_EXISTS``).
            device_id: The device to install on (if not given, all connected devices are used).
            installer: The package name of the app performing the installation (e.g. ``com.android.vending``).
            originating_uri: The URI of the app performing the installation.
            adb_path: Path to the ``adb`` executable (if not in ``PATH``).

        Raises:
            AdbNotFoundError: If ``adb`` is not installed.
            AdbError: If the ``adb`` command failed.
        """
        from .install import install_apks

        with tempfile.TemporaryDirectory(prefix="apkfile-") as tmp_dir:
            apk_paths = []
            base_path = Path(tmp_dir) / (
                PurePosixPath(self._base_name).name or "base.apk"
            )
            base_path.write_bytes(self.base.get_raw())
            apk_paths.append(base_path)
            for i, split in enumerate(self.splits):
                split_path = Path(tmp_dir) / (split._name or f"split_{i}.apk")
                split_path.write_bytes(split.get_raw())
                apk_paths.append(split_path)

            install_apks(
                apks=apk_paths,
                check=check,
                upgrade=upgrade,
                device_id=device_id,
                installer=installer,
                originating_uri=originating_uri,
                adb_path=adb_path,
            )

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the bundle."""
        return {
            field: _jsonable(getattr(self, field))
            for field in (*self._BASE_FIELDS, *self._EXTRA_FIELDS)
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(pkg={self.package_name!r}, version={self.version_code!r}, "
            f"splits={len(self.splits)})"
        )


class ApkmFile(_BaseBundle):
    """
    An `APKMirror Installer <https://www.apkmirror.com/>`_ ``.apkm`` bundle: a base apk + splits + ``info.json``.

    From `fileinfo.com <https://fileinfo.com/extension/xapk>`_: An APKM file is an Android app bundle created
    for use with APKMirror Installer. It is similar to an ``.aab`` file, in that it contains a number of
    ``.apk`` files used to install an Android app.

    >>> apkm = ApkmFile("/home/user/chrome.apkm")
    >>> for split in apkm.splits:
    ...     print(split.split_name)
    >>> apkm.install(upgrade=True)

    Attributes:
        base: The base apk.
        splits: The split apks.
        app_name: The app's name, as recorded by APKMirror.
        apkm_version: The version of the ``.apkm`` format itself.

    See :class:`~apkfile.ApkFile` for the rest of the shared attributes (``package_name``, ``version_code``, ...).
    """

    _EXTRA_FIELDS = ("app_name", "apkm_version")
    app_name: str
    apkm_version: int

    def __init__(
        self, path: str | os.PathLike[str], *, skip_broken_splits: bool = False
    ) -> None:
        """
        Args:
            path: Path to the ``.apkm`` file.
            skip_broken_splits: If ``True``, broken split apks are skipped instead of raising.

        Raises:
            FileNotFoundError: If the file does not exist.
            InvalidBundleError: If the file is not a valid ``.apkm`` bundle.
        """
        super().__init__(
            path=path,
            manifest_name="info.json",
            base_apk_name="base.apk",
            icon_name="icon.png",
            manifest_attrs={
                "app_name": ("app_name", str, True),
                "apkm_version": ("apkm_version", int, True),
                "package_name": ("pname", str, True),
                "version_code": ("versioncode", int, True),
                "min_sdk_version": ("min_api", int, True),
                "version_name": ("release_version", str, False),
            },
            skip_broken_splits=skip_broken_splits,
        )


class XapkFile(_BaseBundle):
    """
    An `APKPure <https://apkpure.com/>`_ ``.xapk`` bundle: a base apk + splits + ``manifest.json``.

    From `fileinfo.com <https://fileinfo.com/extension/xapk>`_: An XAPK file is a package used to install
    Android apps, similar to ``.apk`` but may contain other assets such as an ``.obb`` file.

    >>> xapk = XapkFile("/home/user/telegram.xapk")
    >>> for split in xapk.splits:
    ...     print(split.split_name)
    >>> xapk.install(upgrade=True)

    Attributes:
        base: The base apk.
        splits: The split apks.
        app_name: The app's name, as recorded by APKPure.
        xapk_version: The version of the ``.xapk`` format itself.

    See :class:`~apkfile.ApkFile` for the rest of the shared attributes (``package_name``, ``version_code``, ...).
    """

    _EXTRA_FIELDS = ("app_name", "xapk_version")
    app_name: str
    xapk_version: int

    def __init__(
        self, path: str | os.PathLike[str], *, skip_broken_splits: bool = False
    ) -> None:
        """
        Args:
            path: Path to the ``.xapk`` file.
            skip_broken_splits: If ``True``, broken split apks are skipped instead of raising.

        Raises:
            FileNotFoundError: If the file does not exist.
            InvalidBundleError: If the file is not a valid ``.xapk`` bundle.
        """
        super().__init__(
            path=path,
            manifest_name="manifest.json",
            base_apk_name="{package_name}.apk",
            icon_name="icon.png",
            manifest_attrs={
                "app_name": ("name", str, True),
                "xapk_version": ("xapk_version", int, True),
                "package_name": ("package_name", str, True),
                "version_code": ("version_code", int, True),
                "min_sdk_version": ("min_sdk_version", int, True),
                "version_name": ("version_name", str, False),
                "target_sdk_version": ("target_sdk_version", int, False),
            },
            skip_broken_splits=skip_broken_splits,
        )


class ApksFile(_BaseBundle):
    """
    A `bundletool <https://developer.android.com/tools/bundletool>`_ ``.apks`` set (as produced for e.g.
    `SAI <https://github.com/Aefyr/SAI/>`_): a base apk + splits + ``meta.sai_v{1,2}.json``.

    From `fileinfo.com <https://fileinfo.com/extension/apks>`_: An APKS file is an APK set archive, a
    compressed zip file containing a set of ``.apk`` files split by device characteristics (architecture,
    language, screen density, ...).

    >>> apks = ApksFile("/home/user/facebook.apks")
    >>> for split in apks.splits:
    ...     print(split.split_name)
    >>> apks.install(upgrade=True)

    Attributes:
        base: The base apk.
        splits: The split apks.
        app_name: The app's label, as recorded in the ``.apks`` meta file.
        meta_version: The version of the SAI meta file format (``1`` or ``2``).

    See :class:`~apkfile.ApkFile` for the rest of the shared attributes (``package_name``, ``version_code``, ...).
    """

    _EXTRA_FIELDS = ("app_name", "meta_version")
    app_name: str
    meta_version: int

    def __init__(
        self, path: str | os.PathLike[str], *, skip_broken_splits: bool = False
    ) -> None:
        """
        Args:
            path: Path to the ``.apks`` file.
            skip_broken_splits: If ``True``, broken split apks are skipped instead of raising.

        Raises:
            FileNotFoundError: If the file does not exist.
            InvalidBundleError: If the file is not a valid ``.apks`` set.
        """
        manifest_attrs: dict[str, _ManifestAttr] = {
            "package_name": ("package", str, True),
            "app_name": ("label", str, True),
            "version_code": ("version_code", int, True),
            "version_name": ("version_name", str, False),
            "min_sdk_version": ("min_sdk", int, False),
            "target_sdk_version": ("target_sdk", int, False),
            "meta_version": ("meta_version", int, False),
        }
        try:
            super().__init__(
                path=path,
                manifest_name="meta.sai_v2.json",
                base_apk_name="base.apk",
                icon_name="icon.png",
                manifest_attrs=manifest_attrs,
                skip_broken_splits=skip_broken_splits,
            )
        except InvalidBundleError:
            super().__init__(
                path=path,
                manifest_name="meta.sai_v1.json",
                base_apk_name="base.apk",
                icon_name="icon.png",
                manifest_attrs=manifest_attrs,
                skip_broken_splits=skip_broken_splits,
            )
            self.meta_version = 1
