"""apkfile — read metadata from, and install, ``.apk``/``.apkm``/``.xapk``/``.apks`` files."""

from __future__ import annotations

from datetime import datetime, timezone

import loguru

from ._apk import ApkFile
from ._bundle import ApkmFile, ApksFile, XapkFile
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
    InvalidApkError,
    InvalidBundleError,
)
from .install import install_apks

# androguard logs very verbosely via loguru by default; keep apkfile quiet unless the caller
# explicitly re-enables it with `loguru.logger.enable("androguard")`.
loguru.logger.disable("androguard")

__all__ = [
    "Abi",
    "AdbError",
    "AdbNotFoundError",
    "ApkDiff",
    "ApkFile",
    "ApkFileError",
    "ApkmFile",
    "ApksFile",
    "Certificate",
    "ComponentType",
    "DeepLink",
    "DensityBucket",
    "DexInfo",
    "ExportedComponent",
    "FormFactor",
    "Icon",
    "ImpliedPermission",
    "InstallLocation",
    "InvalidApkError",
    "InvalidBundleError",
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
]

__copyright__ = f"Copyright {datetime.now(timezone.utc).year} David Lev"
__license__ = "MIT"
__title__ = "apkfile"
__version__ = "1.0.1"
