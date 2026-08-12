"""apkfile — read metadata from, and install, ``.apk``/``.apkm``/``.xapk``/``.apks`` files."""

from __future__ import annotations

from datetime import datetime, timezone

import loguru

from ._apk import ApkFile
from ._bundle import ApkmFile, ApksFile, XapkFile
from .abi import Abi
from .enums import InstallLocation, SplitType
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
    "ApkFile",
    "ApkFileError",
    "ApkmFile",
    "ApksFile",
    "InstallLocation",
    "InvalidApkError",
    "InvalidBundleError",
    "SplitType",
    "XapkFile",
    "install_apks",
]

__copyright__ = f"Copyright {datetime.now(timezone.utc).year} David Lev"
__license__ = "MIT"
__title__ = "apkfile"
__version__ = "1.0.0"
