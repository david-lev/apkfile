"""Installing apks on a device via ``adb``."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Sequence

from ._apk import ApkFile
from .abi import Abi
from .enums import SplitType
from .exceptions import AdbError, AdbNotFoundError, InvalidApkError

__all__ = ["install_apks"]

# Standard Android screen-density buckets, keyed by the suffix used in split apk names
# (e.g. a split named "config.xxhdpi").
_DPI_BUCKETS = {
    "ldpi": 120,
    "mdpi": 160,
    "hdpi": 240,
    "xhdpi": 320,
    "xxhdpi": 480,
    "xxxhdpi": 640,
}


def _find_adb(adb_path: str | os.PathLike[str] | None) -> str:
    path = os.fspath(adb_path) if adb_path is not None else shutil.which("adb")
    if path is None:
        raise AdbNotFoundError(
            "adb is not installed or not in PATH. See https://developer.android.com/studio/command-line/adb"
        )
    return path


def _apk_path(apk: ApkFile) -> str:
    """`apk.path` is only ever `None` for apks parsed from raw bytes; every apk here was
    constructed straight from a real path, so this narrows `str | None` down to `str`."""
    assert apk.path is not None
    return apk.path


def _run(args: Sequence[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise AdbError((e.stderr or e.stdout or str(e)).strip()) from e
    return result.stdout


def install_apks(
    apks: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
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
    Install apk(s) on android device(s) using `adb <https://developer.android.com/studio/command-line/adb>`_.

    ``check`` is ``True`` by default, meaning the app(s) are checked for compatibility with the device(s)
    before installing — comparing ``min_sdk_version``, ``abis``, and locale/density splits against the
    device's capabilities.

    >>> install_apks("path/to/apk.apk")
    >>> install_apks(
    ...     ["path/to/base.apk", "path/to/split.apk"],
    ...     device_id="emulator-5554",
    ...     skip_broken=True,
    ... )
    >>> install_apks(
    ...     "path/to/apk.apk",
    ...     check=False,
    ...     installer="com.android.vending",
    ...     upgrade=True,
    ... )

    Args:
        apks: The path to an apk, or an iterable of paths (a base apk + its splits).
        check: Check that the app(s) are compatible with the device(s) before installing.
        upgrade: Whether to upgrade the app if it's already installed (``INSTALL_FAILED_ALREADY_EXISTS``).
        device_id: The id of the device to install on (if not given, all connected devices are used).
        skip_broken: Skip apks that fail to parse instead of raising (only relevant when ``check=True``).
        installer: The package name of the app performing the installation (e.g. ``com.android.vending``).
        originating_uri: The URI of the app performing the installation.
        adb_path: Path to the ``adb`` executable (if not in ``PATH``).

    Raises:
        AdbNotFoundError: If ``adb`` is not installed.
        AdbError: If an ``adb`` command failed.
        InvalidApkError: If ``check`` is ``True``, ``skip_broken`` is ``False``, and one of the apks is invalid.
    """
    adb = _find_adb(adb_path)
    apk_paths = (
        [os.fspath(apks)]
        if isinstance(apks, (str, os.PathLike))
        else [os.fspath(a) for a in apks]
    )

    if device_id is None:
        devices = tuple(
            line.split("\t")[0]
            for line in _run((adb, "devices")).strip().split("\n")[1:]
            if line.endswith("device")
        )
    else:
        devices = (device_id,)

    for device in devices:
        adb_args = (adb, "-s", device)
        tmp_dir = _run(
            (*adb_args, "shell", "mktemp", "-d", "--tmpdir=/data/local/tmp")
        ).strip()

        if check:
            apks_to_install = _resolve_apks_to_install(
                apk_paths=apk_paths, adb_args=adb_args, skip_broken=skip_broken
            )
            if not apks_to_install:
                continue
        else:
            apks_to_install = {path: os.path.getsize(path) for path in apk_paths}

        try:
            _run((*adb_args, "push", *apks_to_install, tmp_dir))
            create_output = _run(
                (
                    *adb_args,
                    "shell",
                    "pm",
                    "install-create",
                    *(("-r",) if upgrade else ()),
                    *(("-i", installer) if installer else ()),
                    *(
                        ("--originating-uri", originating_uri)
                        if originating_uri
                        else ()
                    ),
                    "-S",
                    str(sum(apks_to_install.values())),
                )
            )
            session_match = re.search(r"\d+", create_output)
            if session_match is None:
                raise AdbError(
                    f"Could not parse an install session id from: {create_output!r}"
                )
            session_id = session_match.group(0)

            for idx, (apk_path, size) in enumerate(apks_to_install.items()):
                basename = os.path.basename(apk_path)
                _run(
                    (
                        *adb_args,
                        "shell",
                        "pm",
                        "install-write",
                        "-S",
                        str(size),
                        session_id,
                        str(idx),
                        f"{tmp_dir}/{basename}",
                    )
                )
            _run((*adb_args, "shell", "pm", "install-commit", session_id))
        except AdbError as e:
            raise AdbError(f"Failed to install apk(s) on device {device!r}: {e}") from e
        finally:
            _run((*adb_args, "shell", "rm", "-rf", tmp_dir))


def _resolve_apks_to_install(
    *, apk_paths: list[str], adb_args: tuple[str, ...], skip_broken: bool
) -> dict[str, int]:
    """Parse ``apk_paths`` and pick the subset compatible with the device targeted by ``adb_args``."""
    all_apks: list[ApkFile] = []
    for apk_path in apk_paths:
        try:
            all_apks.append(ApkFile(apk_path))
        except InvalidApkError:
            if not skip_broken:
                raise
    if not all_apks:
        return {}

    lang_splits = tuple(a for a in all_apks if a.split_type == SplitType.LANGUAGE)
    dpi_splits = tuple(a for a in all_apks if a.split_type == SplitType.DPI)
    abi_splits = tuple(a for a in all_apks if a.split_type == SplitType.ABI)
    others = tuple(
        a for a in all_apks if a not in (*lang_splits, *dpi_splits, *abi_splits)
    )

    apks_to_install: dict[str, int] = {}

    device_abis = tuple(
        Abi(abi)
        for abi in _run((*adb_args, "shell", "getprop", "ro.product.cpu.abilist"))
        .strip()
        .split(",")
    )
    device_sdk = int(
        _run((*adb_args, "shell", "getprop", "ro.build.version.sdk")).strip()
    )

    for apk in others:
        sdk_ok = apk.min_sdk_version is None or apk.min_sdk_version <= device_sdk
        abi_ok = not apk.abis or any(
            device_abi.is_compatible_with(apk_abi)
            for apk_abi in apk.abis
            for device_abi in device_abis
        )
        if sdk_ok and abi_ok:
            apks_to_install[_apk_path(apk)] = apk.size
    if not apks_to_install:
        return {}

    if abi_splits:
        device_main_abi = Abi(
            _run((*adb_args, "shell", "getprop", "ro.product.cpu.abi")).strip()
        )
        abi_split = next(
            (
                split
                for split in abi_splits
                if split.abis and device_main_abi == split.abis[0]
            ),
            None,
        )
        if abi_split is None:
            return {}
        apks_to_install[_apk_path(abi_split)] = abi_split.size

    if lang_splits:
        device_lang = (
            _run((*adb_args, "shell", "getprop", "persist.sys.locale"))
            .strip()
            .split("-")[0]
        )
        matched = [
            split
            for split in lang_splits
            if any(device_lang in lang for lang in split.langs)
        ]
        for split in matched or lang_splits:  # fall back to installing every lang split
            apks_to_install[_apk_path(split)] = split.size

    if dpi_splits:
        device_dpi = int(
            _run((*adb_args, "shell", "getprop", "ro.sf.lcd_density")).strip()
        )
        best: tuple[int, ApkFile] | None = None
        for split in dpi_splits:
            bucket = (
                _DPI_BUCKETS.get(split.split_name.rsplit(".", 1)[-1])
                if split.split_name
                else None
            )
            if bucket is None:
                continue
            if best is None or abs(bucket - device_dpi) < abs(best[0] - device_dpi):
                best = (bucket, split)
        if best is not None:
            apks_to_install[_apk_path(best[1])] = best[1].size

    return apks_to_install
