"""``ApkFile`` — a single ``.apk``, parsed in-process with androguard (no ``aapt`` involved)."""

from __future__ import annotations

import dataclasses
import hashlib
import io
import os
import re
import struct
import tempfile
import zipfile
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from androguard.core.apk import APK as _AndroguardAPK

from ._security import SecurityInfo, build_security_info
from ._signing import SigningInfo, build_signing_info
from ._size import DexInfo, SizeBreakdown, build_dex_info, build_size_breakdown
from .abi import Abi
from .enums import InstallLocation, SplitType, classify_split
from .exceptions import ApkFileError, InvalidApkError

if TYPE_CHECKING:
    from .diff import ApkDiff

__all__ = ["ApkFile"]

# lxml's `_Element` isn't cleanly importable for typing purposes (no py.typed / stub package),
# so manifest XML nodes are typed as `Any` rather than reaching for lxml's private class.
_XmlElement = Any

_ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
_HASH_CHUNK_SIZE = 1024 * 1024
_SCREEN_SIZE_ATTRS = ("smallScreens", "normalScreens", "largeScreens", "xlargeScreens")

# androguard can raise a handful of low-level errors when handed a corrupt (but zip-readable)
# file. `OSError` (and its `FileNotFoundError` subclass) is deliberately excluded so that a
# missing path still raises a plain `FileNotFoundError`, as callers would expect.
_PARSE_ERRORS = (
    ValueError,
    zipfile.BadZipFile,
    struct.error,
    IndexError,
    KeyError,
    EOFError,
)


def _jsonable(value: Any) -> Any:
    """Recursively convert dataclass instances (e.g. :class:`SigningInfo`) into plain dicts/lists,
    so :meth:`ApkFile.as_dict` output round-trips cleanly through ``json.dumps``."""
    return dataclasses.asdict(value) if dataclasses.is_dataclass(value) else value


def _load_apk(source: Path | bytes, *, raw: bool, display_name: str) -> _AndroguardAPK:
    try:
        # androguard's own type hints only declare `filename: str`, but it accepts a `Path`
        # (confirmed hands-on) and raw bytes when `raw=True` (see its class docstring's
        # `APK(read("myfile.apk"), raw=True)`).
        apk = _AndroguardAPK(source, raw=raw)  # ty: ignore[invalid-argument-type]
    except _PARSE_ERRORS as e:
        raise InvalidApkError(f"{display_name!r} is not a valid APK file: {e}") from e
    if not apk.is_valid_APK():
        raise InvalidApkError(f"{display_name!r} is not a valid APK file")
    return apk


class ApkFile:
    """
    A single Android ``.apk`` file.

    From `fileinfo.com <https://fileinfo.com/extension/apk>`_: An APK file is an app created for Android,
    Google's mobile operating system.
    `APK on Wikipedia ↗️ <https://en.wikipedia.org/wiki/Apk_(file_format)>`_.

    All metadata is read directly from ``AndroidManifest.xml``/``resources.arsc`` (via
    `androguard <https://github.com/androguard/androguard>`_) — no external binary is required.

    >>> apk = ApkFile("/home/user/whatsapp.apk")
    >>> apk.package_name, apk.version_code, apk.version_name
    >>> apk.install(upgrade=True)

    Attributes:
        path: Path to the ``.apk`` file, or ``None`` if this instance was constructed from raw bytes
            (e.g. a split read out of a bundle) and hasn't been :meth:`save`\\ d to disk yet.
        package_name: The package name of an Android app uniquely identifies the app on the device, in
            Google Play Store, and in supported third-party Android stores.
            `↗️ <https://support.google.com/admob/answer/9972781>`_
        version_code: An incremental integer value that represents the version of the application code.
            `↗️ <https://developer.android.com/studio/publish/versioning#appversioning>`_
        version_name: A string value that represents the release version of the application code.
        min_sdk_version: The minimum version of the Android platform on which the app will run.
        target_sdk_version: The API level on which the app is designed to run.
        install_location: Where the application can be installed: external storage, internal only, or auto.
        labels: A mapping of locale (``""`` for the default locale) to the app's user-visible label in
            that locale.
        permissions: System permissions the app requests.
        libraries: Shared libraries the app must be linked against.
        features: Hardware/software features the app uses.
        launchable_activity: The app's main/launcher activity, if any.
        supported_screens: Screen sizes the app declares support for (``small``/``normal``/``large``/``xlarge``).
        supports_any_density: Whether the app includes resources to accommodate any screen density.
        langs: Locales the app has resources for.
        densities: Screen density buckets (dpi) the app ships an icon asset for.
        abis: Native ABIs the app ships native libraries for (from ``lib/<abi>/...``).
        icons: Mapping of density (dpi) to the in-archive path of the icon asset for that density.
        split_name: The ``split`` name of this APK, if it is a split APK.
        is_split: Whether this is a split APK.
        split_type: What the split varies by (language/dpi/abi/other), if :attr:`is_split`.
        size: The file size in bytes.
        md5: The MD5 hash of the APK's bytes.
        sha256: The SHA256 hash of the APK's bytes.
        signing: Signing scheme(s) and certificate(s) this APK was signed with.
        security: Manifest security posture — permissions, exported components, deep links.
        size_breakdown: On-disk size, broken down by content category (dex/resources/native libs/...).
        dex_info: Method/class/string counts across the APK's ``classesN.dex`` files.
    """

    _apk: _AndroguardAPK
    path: Path | None

    def __init__(self, path: str | os.PathLike[str]) -> None:
        """
        Args:
            path: Path to the ``.apk`` file.

        Raises:
            FileNotFoundError: If the file does not exist.
            InvalidApkError: If the file is not a valid APK.
        """
        self.path = Path(path)
        self._name = self.path.name
        self._apk = _load_apk(self.path, raw=False, display_name=str(self.path))

    @classmethod
    def _from_bytes(cls, data: bytes, *, name: str) -> ApkFile:
        """Construct an :class:`ApkFile` from raw bytes, without touching disk (used for bundle splits)."""
        self = cls.__new__(cls)
        self.path = None
        self._name = name
        self._apk = _load_apk(data, raw=True, display_name=name)
        return self

    @cached_property
    def _manifest_root(self) -> _XmlElement:
        root = self._apk.get_android_manifest_xml()
        if root is None:
            raise InvalidApkError(f"{self._name!r} has no readable AndroidManifest.xml")
        return root

    # -- basic manifest fields -------------------------------------------------------------

    @cached_property
    def package_name(self) -> str:
        return self._apk.get_package()

    @cached_property
    def version_code(self) -> int:
        return int(self._apk.get_androidversion_code())

    @cached_property
    def version_name(self) -> str | None:
        return self._apk.get_androidversion_name()

    @cached_property
    def min_sdk_version(self) -> int | None:
        value = self._apk.get_min_sdk_version()
        return int(value) if value is not None else None

    @cached_property
    def target_sdk_version(self) -> int | None:
        value = self._apk.get_target_sdk_version()
        return int(value) if value is not None else None

    @cached_property
    def install_location(self) -> InstallLocation:
        return InstallLocation(self._manifest_root.get(_ANDROID_NS + "installLocation"))

    @cached_property
    def permissions(self) -> tuple[str, ...]:
        return tuple(self._apk.get_permissions())

    @cached_property
    def libraries(self) -> tuple[str, ...]:
        return tuple(self._apk.get_libraries())

    @cached_property
    def features(self) -> tuple[str, ...]:
        return tuple(self._apk.get_features())

    @cached_property
    def launchable_activity(self) -> str | None:
        return self._apk.get_main_activity()

    # -- resource-table-derived fields -------------------------------------------------------

    @cached_property
    def _resource_package_name(self) -> str | None:
        arsc = self._apk.get_android_resources()
        if arsc is None:
            return None
        names = arsc.get_packages_names()
        return names[0] if names else None

    @cached_property
    def labels(self) -> dict[str, str]:
        arsc = self._apk.get_android_resources()
        pkg = self._resource_package_name
        if arsc is None or pkg is None:
            default = self._apk.get_app_name()
            return {"": default} if default else {}
        labels: dict[str, str] = {}
        for locale in arsc.get_locales(pkg):
            label = self._apk.get_app_name(locale=locale)
            if label:
                labels["" if locale in ("\x00\x00", "") else locale] = label
        return labels

    @cached_property
    def langs(self) -> tuple[str, ...]:
        arsc = self._apk.get_android_resources()
        pkg = self._resource_package_name
        if arsc is None or pkg is None:
            return ()
        return tuple(
            sorted(loc for loc in arsc.get_locales(pkg) if loc and loc != "\x00\x00")
        )

    @cached_property
    def icons(self) -> dict[int, str]:
        application = self._manifest_root.find("application")
        icon_ref = (
            application.get(_ANDROID_NS + "icon") if application is not None else None
        )
        if not icon_ref or not icon_ref.startswith("@"):
            return {}
        try:
            resource_id = int(icon_ref[1:], 16)
        except ValueError:
            return {}
        arsc = self._apk.get_android_resources()
        if arsc is None:
            return {}
        icons: dict[int, str] = {}
        # androguard's type hints declare `list[ARSCResTableConfig]`, but this actually returns
        # `list[tuple[ARSCResTableConfig, ARSCResStringPoolEntry]]` at runtime.
        for config, _entry in arsc.get_res_configs(resource_id):  # ty: ignore[not-iterable]
            density = config.get_density()
            if not density:
                continue
            path = self._apk.get_app_icon(max_dpi=density)
            if path:
                icons[density] = path
        return dict(sorted(icons.items()))

    @cached_property
    def densities(self) -> tuple[int, ...]:
        return tuple(self.icons.keys())

    @cached_property
    def abis(self) -> tuple[Abi, ...]:
        found: set[Abi] = set()
        for name in self._apk.get_files():
            parts = name.split("/")
            if len(parts) >= 3 and parts[0] == "lib":
                found.add(Abi(parts[1]))
        return tuple(sorted(found, key=lambda abi: abi.value))

    # -- <supports-screens> -----------------------------------------------------------------

    @cached_property
    def _supports_screens_element(self) -> _XmlElement | None:
        return self._manifest_root.find("supports-screens")

    @cached_property
    def supported_screens(self) -> tuple[str, ...]:
        element = self._supports_screens_element
        if element is None:
            return ()
        return tuple(
            attr[: -len("Screens")].lower()
            for attr in _SCREEN_SIZE_ATTRS
            if element.get(_ANDROID_NS + attr) == "true"
        )

    @cached_property
    def supports_any_density(self) -> bool:
        element = self._supports_screens_element
        if element is None:
            return False
        return element.get(_ANDROID_NS + "anyDensity") == "true"

    # -- splits -------------------------------------------------------------------------------

    @cached_property
    def split_name(self) -> str | None:
        return self._manifest_root.get("split")

    @cached_property
    def is_split(self) -> bool:
        return self.split_name is not None

    @cached_property
    def split_type(self) -> SplitType | None:
        if self.split_name is None:
            return None
        return classify_split(self.split_name, self.langs, self.abis)

    # -- file-ish operations --------------------------------------------------------------

    def get_raw(self) -> bytes:
        """Get the raw bytes of this apk."""
        return self._apk.get_raw()

    @property
    def size(self) -> int:
        """The file size in bytes."""
        if self.path is not None:
            return self.path.stat().st_size
        return len(self.get_raw())

    def _hash(self, algorithm: str) -> str:
        digest = hashlib.new(algorithm)
        if self.path is not None:
            with self.path.open("rb") as f:
                for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
                    digest.update(chunk)
        else:
            digest.update(self.get_raw())
        return digest.hexdigest()

    @cached_property
    def md5(self) -> str:
        """The MD5 hash of the APK's bytes."""
        return self._hash("md5")

    @cached_property
    def sha256(self) -> str:
        """The SHA256 hash of the APK's bytes."""
        return self._hash("sha256")

    @cached_property
    def signing(self) -> SigningInfo:
        """This APK's signing scheme(s) and certificate(s)."""
        return build_signing_info(self._apk)

    @cached_property
    def security(self) -> SecurityInfo:
        """This APK's manifest security posture (permissions, exported components, deep links)."""
        return build_security_info(self._apk, self._manifest_root)

    @cached_property
    def size_breakdown(self) -> SizeBreakdown:
        """This APK's on-disk size, broken down by content category."""
        with self.as_zip_file() as zf:
            return build_size_breakdown(zf)

    @cached_property
    def dex_info(self) -> DexInfo:
        """Method/class/string counts across this APK's ``classesN.dex`` files."""
        return build_dex_info(self._apk)

    def diff(self, other: ApkFile) -> ApkDiff:
        """Compare this apk against ``other``. See :func:`apkfile.diff.diff`."""
        from .diff import diff as _diff

        return _diff(self, other)

    def as_zip_file(self) -> zipfile.ZipFile:
        """Get the apk as a :class:`zipfile.ZipFile` (from disk if :attr:`path` is set, else from memory)."""
        if self.path is not None:
            return zipfile.ZipFile(self.path)
        return zipfile.ZipFile(io.BytesIO(self.get_raw()))

    def extract(
        self, path: str | os.PathLike[str], members: Iterable[str] | None = None
    ) -> None:
        """
        Extract files from within the apk to a directory.

        >>> apk.extract(path="out", members=["AndroidManifest.xml"])

        Args:
            path: Path to the directory to extract to.
            members: An optional list of names to extract. If not provided, all files will be extracted.
        """
        with self.as_zip_file() as zf:
            zf.extractall(path=path, members=members)

    def save(self, path: str | os.PathLike[str]) -> None:
        """
        Write this APK's bytes to ``path``, and update :attr:`path` to point there.

        This is mainly useful for :class:`ApkFile` instances obtained from a bundle's ``base``/``splits``,
        which have ``path is None`` until saved.
        """
        target = Path(path)
        target.write_bytes(self.get_raw())
        self.path = target

    def rename(self, name: str) -> None:
        """
        Rename the file on disk.

        >>> apk.rename("{package_name}-{version_code}.apk")

        Args:
            name: The new name of the file. Can contain ``{attr}`` format fields for any str/int attribute.

        Raises:
            ApkFileError: If this instance has no :attr:`path` yet (call :meth:`save` first).
            TypeError: If a format field isn't a str/int attribute of this instance.
        """
        if self.path is None:
            raise ApkFileError("Cannot rename an APK with no path; call save() first.")
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
        self.path = self.path.rename(new_path)

    def install(
        self,
        *,
        check: bool = True,
        upgrade: bool = False,
        device_id: str | None = None,
        skip_broken: bool = False,
        installer: str | None = None,
        originating_uri: str | None = None,
        adb_path: str | os.PathLike[str] | None = None,
    ) -> None:
        """
        Install this apk on a device using `adb <https://developer.android.com/studio/command-line/adb>`_.

        Args:
            check: Check that the app is compatible with the device before installing.
            upgrade: Whether to upgrade the app if it's already installed (``INSTALL_FAILED_ALREADY_EXISTS``).
            device_id: The device to install on (if not given, all connected devices are used).
            skip_broken: Skip broken apks instead of raising.
            installer: The package name of the app performing the installation (e.g. ``com.android.vending``).
            originating_uri: The URI of the app performing the installation.
            adb_path: Path to the ``adb`` executable (if not in ``PATH``).

        Raises:
            AdbNotFoundError: If ``adb`` is not installed.
            AdbError: If the ``adb`` command failed.
        """
        from .install import install_apks

        if self.path is not None:
            install_apks(
                apks=self.path,
                check=check,
                upgrade=upgrade,
                device_id=device_id,
                skip_broken=skip_broken,
                installer=installer,
                originating_uri=originating_uri,
                adb_path=adb_path,
            )
            return
        with tempfile.TemporaryDirectory(prefix="apkfile-") as tmp_dir:
            name = self._name if self._name.endswith(".apk") else f"{self._name}.apk"
            tmp_path = Path(tmp_dir) / name
            tmp_path.write_bytes(self.get_raw())
            install_apks(
                apks=tmp_path,
                check=check,
                upgrade=upgrade,
                device_id=device_id,
                skip_broken=skip_broken,
                installer=installer,
                originating_uri=originating_uri,
                adb_path=adb_path,
            )

    _FIELDS: tuple[str, ...] = (
        "path",
        "package_name",
        "version_code",
        "version_name",
        "min_sdk_version",
        "target_sdk_version",
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
        "icons",
        "split_name",
        "is_split",
        "split_type",
        "size",
        "md5",
        "sha256",
        "signing",
        "security",
        "size_breakdown",
        "dex_info",
    )

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the apk file."""
        return {field: _jsonable(getattr(self, field)) for field in self._FIELDS}

    def __repr__(self) -> str:
        split = f", split={self.split_name!r}" if self.is_split else ""
        return f"{self.__class__.__name__}(pkg={self.package_name!r}, version={self.version_code!r}{split})"
