"""Exception hierarchy raised by apkfile."""

from __future__ import annotations

__all__ = [
    "AdbError",
    "AdbNotFoundError",
    "ApkFileError",
    "InvalidApkError",
    "InvalidBundleError",
]


class ApkFileError(Exception):
    """Base class for all exceptions raised by apkfile."""


class InvalidApkError(ApkFileError):
    """Raised when a `.apk` file is corrupt, or not an APK at all."""


class InvalidBundleError(ApkFileError):
    """Raised when a `.apkm`/`.xapk`/`.apks` archive is corrupt or missing its manifest."""


class AdbError(ApkFileError):
    """Raised when an `adb` command fails."""


class AdbNotFoundError(ApkFileError):
    """Raised when `adb` cannot be found in `PATH` (and no `adb_path` was given)."""
