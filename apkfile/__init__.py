"""apkfile — read metadata from, and install, `.apk`/`.apkm`/`.xapk`/`.apks`/`.apkv` files."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

import loguru

from ._apk import ApkFile
from ._apkv import ApkvFile
from ._bundle import ApkmFile, ApksFile, XapkFile
from ._obb import ObbFile
from ._resources import DensityBucket, Icon, ScreenSize
from ._security import (
    ComponentType,
    DeepLink,
    ExportedComponent,
    ImpliedPermission,
    PermissionInfo,
    ProtectionLevel,
    SecurityInfo,
)
from ._signing import Certificate, SigningInfo, SigningScheme
from ._size import DexInfo, SizeBreakdown
from .abi import Abi
from .diff import ApkDiff, diff
from .enums import FormFactor, InstallLocation, SplitType
from .exceptions import (
    AdbError,
    AdbNotFoundError,
    ApkFileError,
    EncryptedBundleError,
    InvalidApkError,
    InvalidBundleError,
)
from .install import install_apks, uninstall_apks

# Both androguard and apkfile itself log via loguru. androguard is very verbose by default, and
# apkfile's own logging is opt-in (mirrors the standard library's logging philosophy: a library
# should be silent unless its caller asks for output) — so both are disabled here, and re-enabled
# with `loguru.logger.enable("androguard")` / `loguru.logger.enable("apkfile")` (the CLI's
# `--verbose`/`-v` flag does the latter, plus attaches a colorized sink).
loguru.logger.disable("androguard")
loguru.logger.disable("apkfile")

__all__ = [
    "Abi",
    "AdbError",
    "AdbNotFoundError",
    "ApkDiff",
    "ApkFile",
    "ApkFileError",
    "ApkmFile",
    "ApksFile",
    "ApkvFile",
    "Certificate",
    "ComponentType",
    "DeepLink",
    "DensityBucket",
    "DexInfo",
    "EncryptedBundleError",
    "ExportedComponent",
    "FormFactor",
    "Icon",
    "ImpliedPermission",
    "InstallLocation",
    "InvalidApkError",
    "InvalidBundleError",
    "ObbFile",
    "PermissionInfo",
    "ProtectionLevel",
    "ScreenSize",
    "SecurityInfo",
    "SigningInfo",
    "SigningScheme",
    "SizeBreakdown",
    "SplitType",
    "XapkFile",
    "diff",
    "install_apks",
    "uninstall_apks",
]

__copyright__ = f"Copyright {datetime.now(timezone.utc).year} David Lev"
__license__ = "MIT"
__title__ = "apkfile"
try:
    # `pyproject.toml`'s `[project] version` is the single source of truth — it's what ends up in
    # the installed distribution's metadata (standard PEP 621 behavior for any build backend,
    # including uv_build), so reading it back from there avoids keeping a second copy in sync here.
    __version__ = _pkg_version("apkfile")
except (
    PackageNotFoundError
):  # pragma: no cover - only when apkfile is used without being installed
    __version__ = "0.0.0+unknown"
