"""Installing/uninstalling apks on a device via `adb`."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ._apk import ApkFile
from ._resources import DensityBucket
from .abi import Abi
from .enums import SplitType
from .exceptions import AdbError, AdbNotFoundError, InvalidApkError

__all__ = ["install_apks", "uninstall_apks"]


def _find_adb(adb_path: str | os.PathLike[str] | None) -> str:
    path = str(Path(adb_path)) if adb_path is not None else shutil.which("adb")
    if path is None:
        raise AdbNotFoundError(
            "adb is not installed or not in PATH. See https://developer.android.com/studio/command-line/adb"
        )
    return path


def _apk_path(apk: ApkFile) -> str:
    """`apk.path` is only ever `None` for apks parsed from raw bytes; every apk here was
    constructed straight from a real path, so this narrows `Path | None` down to `str`."""
    assert apk.path is not None
    return str(apk.path)


def _run(args: Sequence[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise AdbError((e.stderr or e.stdout or str(e)).strip()) from e
    return result.stdout


def _list_devices(adb: str, device_id: str | None) -> tuple[str, ...]:
    if device_id is not None:
        return (device_id,)
    return tuple(
        line.split("\t")[0]
        for line in _run((adb, "devices")).strip().split("\n")[1:]
        if line.endswith("device")
    )


def _run_on_devices(
    devices: tuple[str, ...], worker: Callable[[str], None], *, action: str
) -> None:
    """Run `worker(device)` against every device in parallel (one thread per device — `adb` calls
    are I/O-bound, so this is a plain speedup with no GIL contention).

    Every device is attempted even if others fail — one device's error never skips the rest — and
    if any device(s) failed, a single `AdbError` (`action` in its message) summarizing every
    failure is raised once every device has finished. An `InvalidApkError` (raised by `worker`
    itself, not caught here otherwise) is device-independent — the same broken input apk fails
    identically everywhere — so it's re-raised once instead of folded into that summary.
    """
    errors: dict[str, AdbError] = {}
    invalid_apk_error: InvalidApkError | None = None
    if devices:
        with ThreadPoolExecutor(max_workers=len(devices)) as pool:
            future_to_device = {
                pool.submit(worker, device): device for device in devices
            }
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    future.result()
                except InvalidApkError as e:
                    invalid_apk_error = e
                except AdbError as e:
                    errors[device] = e

    if invalid_apk_error is not None:
        raise invalid_apk_error

    if len(errors) == 1:
        ((device, e),) = errors.items()
        raise AdbError(f"Failed to {action} on device {device!r}: {e}") from e
    if errors:
        summary = "; ".join(f"{dev!r}: {e}" for dev, e in errors.items())
        raise AdbError(
            f"Failed to {action} on {len(errors)}/{len(devices)} device(s): {summary}"
        ) from next(iter(errors.values()))


def install_apks(
    apks: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
    *,
    check: bool = True,
    upgrade: bool = False,
    device_id: str | None = None,
    skip_broken: bool = False,
    installer: str | None = None,
    originating_uri: str | None = None,
    grant_permissions: bool = False,
    allow_downgrade: bool = False,
    allow_test_packages: bool = False,
    user: str | None = None,
    obb_paths: str | os.PathLike[str] | Iterable[str | os.PathLike[str]] | None = None,
    adb_path: str | os.PathLike[str] | None = None,
) -> None:
    """
    Install apk(s) on android device(s) using [adb](https://developer.android.com/studio/command-line/adb).

    `check` is `True` by default, meaning the app(s) are checked for compatibility with the device(s)
    before installing — comparing `min_sdk_version`, `abis`, and locale/density splits against the
    device's capabilities.

    If `device_id` isn't given, every connected device is targeted, in parallel. All devices are
    attempted even if one fails — a failure on one device never skips the rest — and if any
    device(s) failed, a single `AdbError` summarizing every failure is raised once every device
    has finished.

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
    >>> install_apks(
    ...     "path/to/game.apk", obb_paths="path/to/main.1.com.example.game.obb"
    ... )
    >>> install_apks("path/to/apk.apk", grant_permissions=True, allow_downgrade=True)

    Args:
        apks: The path to an apk, or an iterable of paths (a base apk + its splits).
        check: Check that the app(s) are compatible with the device(s) before installing.
        upgrade: Whether to upgrade the app if it's already installed (`INSTALL_FAILED_ALREADY_EXISTS`).
        device_id: The id of the device to install on (if not given, all connected devices are used).
        skip_broken: Skip apks that fail to parse instead of raising (only relevant when `check=True`).
        installer: The package name of the app performing the installation (e.g. `com.android.vending`).
        originating_uri: The URI of the app performing the installation.
        grant_permissions: Grant all runtime permissions the app requests at install time (`pm install -g`).
        allow_downgrade: Allow installing a lower `versionCode` over an existing install (`pm install -d`;
            the device only honors this for a `debuggable` app, regardless of this flag).
        allow_test_packages: Allow installing apps built with `android:testOnly="true"` (`pm install -t`).
        user: Install for a specific user id, or `"all"`/`"current"` (`pm install --user`).
        obb_paths: Path(s) to OBB expansion file(s) to push to `/sdcard/Android/obb/<package>/` after a
            successful install, e.g. for a standalone "apk + obb" pairing that isn't part of a bundle
            (a bundle's own OBBs are already covered by `XapkFile.install()`).
        adb_path: Path to the `adb` executable (if not in `PATH`).

    Raises:
        AdbNotFoundError: If `adb` is not installed.
        AdbError: If an `adb` command failed on one or more devices.
        InvalidApkError: If `check` is `True`, `skip_broken` is `False`, and one of the apks is invalid.
    """
    adb = _find_adb(adb_path)
    apk_paths = (
        [str(Path(apks))]
        if isinstance(apks, (str, os.PathLike))
        else [str(Path(a)) for a in apks]
    )
    obb_local_paths = (
        []
        if obb_paths is None
        else [str(Path(obb_paths))]
        if isinstance(obb_paths, (str, os.PathLike))
        else [str(Path(o)) for o in obb_paths]
    )
    devices = _list_devices(adb, device_id)

    # Resolved once (not per-device) since it's the same for every device and requires parsing an apk.
    obb_package_name = ApkFile(apk_paths[0]).package_name if obb_local_paths else None

    _run_on_devices(
        devices,
        lambda device: _install_on_device(
            device,
            adb=adb,
            apk_paths=apk_paths,
            check=check,
            upgrade=upgrade,
            skip_broken=skip_broken,
            installer=installer,
            originating_uri=originating_uri,
            grant_permissions=grant_permissions,
            allow_downgrade=allow_downgrade,
            allow_test_packages=allow_test_packages,
            user=user,
            obb_local_paths=obb_local_paths,
            obb_package_name=obb_package_name,
        ),
        action="install apk(s)",
    )


def uninstall_apks(
    package_name: str,
    *,
    device_id: str | None = None,
    keep_data: bool = False,
    user: str | None = None,
    version_code: int | None = None,
    adb_path: str | os.PathLike[str] | None = None,
) -> None:
    """
    Uninstall a package from android device(s) using [adb](https://developer.android.com/studio/command-line/adb).

    If `device_id` isn't given, every connected device is targeted, in parallel — same multi-device
    behavior as [`install_apks`][apkfile.install_apks]: every device is attempted even if others
    fail, and a single `AdbError` summarizing every failure is raised once every device has finished.

    >>> uninstall_apks("com.example.app")
    >>> uninstall_apks("com.example.app", device_id="emulator-5554", keep_data=True)

    Args:
        package_name: The package name to uninstall.
        device_id: The id of the device to uninstall from (if not given, all connected devices are used).
        keep_data: Keep the app's data/cache directories after removal (`pm uninstall -k`).
        user: Uninstall for a specific user id only (`pm uninstall --user`).
        version_code: Only uninstall if the installed app has this exact `versionCode`
            (`pm uninstall --versionCode`).
        adb_path: Path to the `adb` executable (if not in `PATH`).

    Raises:
        AdbNotFoundError: If `adb` is not installed.
        AdbError: If an `adb` command failed on one or more devices.
    """
    adb = _find_adb(adb_path)
    devices = _list_devices(adb, device_id)
    _run_on_devices(
        devices,
        lambda device: _uninstall_on_device(
            device,
            adb=adb,
            package_name=package_name,
            keep_data=keep_data,
            user=user,
            version_code=version_code,
        ),
        action=f"uninstall {package_name!r}",
    )


def _uninstall_on_device(
    device: str,
    *,
    adb: str,
    package_name: str,
    keep_data: bool,
    user: str | None,
    version_code: int | None,
) -> None:
    adb_args = (adb, "-s", device)
    _run(
        (
            *adb_args,
            "shell",
            "pm",
            "uninstall",
            *(("-k",) if keep_data else ()),
            *(("--user", user) if user else ()),
            *(("--versionCode", str(version_code)) if version_code is not None else ()),
            package_name,
        )
    )


def _install_on_device(
    device: str,
    *,
    adb: str,
    apk_paths: list[str],
    check: bool,
    upgrade: bool,
    skip_broken: bool,
    installer: str | None,
    originating_uri: str | None,
    grant_permissions: bool,
    allow_downgrade: bool,
    allow_test_packages: bool,
    user: str | None,
    obb_local_paths: list[str],
    obb_package_name: str | None,
) -> None:
    """Install `apk_paths` (+ `obb_local_paths`) on a single device. Runs in its own thread —
    raises `AdbError`/`InvalidApkError` on failure rather than handling it, so the caller can
    attempt every other device before deciding how to report failures."""
    adb_args = (adb, "-s", device)
    tmp_dir: str | None = None
    try:
        tmp_dir = _run(
            (*adb_args, "shell", "mktemp", "-d", "--tmpdir=/data/local/tmp")
        ).strip()

        if check:
            apks_to_install = _resolve_apks_to_install(
                apk_paths=apk_paths, adb_args=adb_args, skip_broken=skip_broken
            )
            if not apks_to_install:
                return
        else:
            apks_to_install = {path: Path(path).stat().st_size for path in apk_paths}

        _run((*adb_args, "push", *apks_to_install, tmp_dir))
        create_output = _run(
            (
                *adb_args,
                "shell",
                "pm",
                "install-create",
                *(("-r",) if upgrade else ()),
                *(("-i", installer) if installer else ()),
                *(("--originating-uri", originating_uri) if originating_uri else ()),
                *(("-g",) if grant_permissions else ()),
                *(("-d",) if allow_downgrade else ()),
                *(("-t",) if allow_test_packages else ()),
                *(("--user", user) if user else ()),
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
            basename = Path(apk_path).name
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

        if obb_local_paths:
            # OBBs aren't part of a pm install session — they're just files in shared storage.
            obb_dir = f"/sdcard/Android/obb/{obb_package_name}"
            _run((*adb_args, "shell", "mkdir", "-p", obb_dir))
            for obb_path in obb_local_paths:
                _run((*adb_args, "push", obb_path, f"{obb_dir}/{Path(obb_path).name}"))
    finally:
        if tmp_dir is not None:
            _run((*adb_args, "shell", "rm", "-rf", tmp_dir))


def _device_lang_codes(adb_args: tuple[str, ...]) -> set[str]:
    """Base language subtags for every locale the device is configured for.

    No single source reliably reflects this across both real, user-configured devices and
    freshly-booted/headless emulators — confirmed hands-on: a stock AVD that never went through
    Setup Wizard leaves `persist.sys.locale(s)` *and* Settings.System's `system_locales`
    completely unset (`getprop`/`settings get` both return nothing useful), even though a real
    device a user has actually set up always has at least one of them populated. Tries
    progressively less-authoritative-but-more-reliably-present sources, in order:

    1. `persist.sys.locales` — the full, priority-ordered locale list (Android 7.0+), when set.
    2. `persist.sys.locale` — the single primary locale, older devices / fallback.
    3. Settings.System's `system_locales` — the live settings-provider value.
    4. `ro.product.locale` — read-only, build-time default. Always present, so this is the
       guaranteed final fallback (matches what a fresh device boots with before any locale is
       ever explicitly configured).
    """
    for cmd in (
        ("getprop", "persist.sys.locales"),
        ("getprop", "persist.sys.locale"),
        ("settings", "get", "system", "system_locales"),
    ):
        raw = _run((*adb_args, "shell", *cmd)).strip()
        if raw and raw != "null":
            break
    else:
        raw = _run((*adb_args, "shell", "getprop", "ro.product.locale")).strip()
    return {lang.split("-")[0] for lang in raw.split(",") if lang}


def _resolve_apks_to_install(
    *, apk_paths: list[str], adb_args: tuple[str, ...], skip_broken: bool
) -> dict[str, int]:
    """Parse `apk_paths` and pick the subset compatible with the device targeted by `adb_args`."""
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
        device_langs = _device_lang_codes(adb_args)
        matched = [
            split
            for split in lang_splits
            if any(
                device_lang in lang
                for device_lang in device_langs
                for lang in split.langs
            )
        ]
        for split in matched or lang_splits:  # fall back to installing every lang split
            apks_to_install[_apk_path(split)] = split.size

    if dpi_splits:
        device_dpi = int(
            _run((*adb_args, "shell", "getprop", "ro.sf.lcd_density")).strip()
        )
        best: tuple[int, ApkFile] | None = None
        for split in dpi_splits:
            bucket_name = (
                split.split_name.rsplit(".", 1)[-1] if split.split_name else None
            )
            try:
                dpi = DensityBucket(bucket_name).dpi if bucket_name else None
            except ValueError:
                dpi = None
            if dpi is None:
                continue
            if best is None or abs(dpi - device_dpi) < abs(best[0] - device_dpi):
                best = (dpi, split)
        if best is not None:
            apks_to_install[_apk_path(best[1])] = best[1].size

    return apks_to_install
