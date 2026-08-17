"""The `apkfile` command-line interface."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ._apk import ApkFile
from ._apkv import ApkvFile
from ._bundle import ApkmFile, ApksFile, XapkFile
from .diff import diff as diff_apks
from .install import install_apks, uninstall_apks

_LOADERS: dict[str, Callable[..., Any]] = {
    ".apk": ApkFile,
    ".apkm": ApkmFile,
    ".xapk": XapkFile,
    ".apks": ApksFile,
    ".apkv": ApkvFile,
}


def _load(path: str, *, password: str | None = None) -> Any:
    suffix = Path(path).suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise SystemExit(
            f"Don't know how to open {path!r} (unrecognized extension {suffix!r})"
        )
    if suffix == ".apkv":
        return loader(path, password=password)
    return loader(path)


def _cmd_info(args: argparse.Namespace) -> None:
    apk = _load(args.path, password=args.password)
    print(json.dumps(apk.as_dict(), indent=2, default=str))


def _cmd_diff(args: argparse.Namespace) -> None:
    a, b = _load(args.a), _load(args.b)
    print(json.dumps(dataclasses.asdict(diff_apks(a, b)), indent=2, default=str))


def _cmd_install(args: argparse.Namespace) -> None:
    install_apks(
        apks=args.paths,
        check=not args.no_check,
        upgrade=args.upgrade,
        device_id=args.device,
        skip_broken=args.skip_broken,
        installer=args.installer,
        originating_uri=args.originating_uri,
        grant_permissions=args.grant_permissions,
        allow_downgrade=args.allow_downgrade,
        allow_test_packages=args.allow_test_packages,
        user=args.user,
        obb_paths=args.obb,
        adb_path=args.adb_path,
    )


def _cmd_uninstall(args: argparse.Namespace) -> None:
    uninstall_apks(
        args.package,
        device_id=args.device,
        keep_data=args.keep_data,
        user=args.user,
        version_code=args.version_code,
        adb_path=args.adb_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apkfile")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="Print an apk/bundle's metadata as JSON")
    info.add_argument("path", help="Path to a .apk/.apkm/.xapk/.apks/.apkv file")
    info.add_argument(
        "--password", default=None, help="Password for an encrypted .apkv archive"
    )
    info.set_defaults(func=_cmd_info)

    diff = subparsers.add_parser(
        "diff", help="Print the differences between two apks/bundles as JSON"
    )
    diff.add_argument("a", help="Path to the baseline .apk/.apkm/.xapk/.apks file")
    diff.add_argument(
        "b", help="Path to the .apk/.apkm/.xapk/.apks file to compare against a"
    )
    diff.set_defaults(func=_cmd_diff)

    install = subparsers.add_parser(
        "install", help="Install apk(s) to connected device(s)"
    )
    install.add_argument(
        "paths", nargs="+", help="Path(s) to .apk file(s) (a base apk + its splits)"
    )
    install.add_argument("--device", default=None, help="Target a specific device id")
    install.add_argument(
        "--upgrade", action="store_true", help="Upgrade if already installed"
    )
    install.add_argument(
        "--no-check", action="store_true", help="Skip device-compatibility checking"
    )
    install.add_argument(
        "--skip-broken",
        action="store_true",
        help="Skip apks that fail to parse instead of raising (only relevant with --check)",
    )
    install.add_argument(
        "--installer",
        default=None,
        help="Package name of the app performing the installation (e.g. com.android.vending)",
    )
    install.add_argument(
        "--originating-uri",
        default=None,
        help="The URI of the app performing the installation",
    )
    install.add_argument(
        "--grant-permissions",
        action="store_true",
        help="Grant all runtime permissions the app requests at install time",
    )
    install.add_argument(
        "--allow-downgrade",
        action="store_true",
        help="Allow installing a lower versionCode over an existing install",
    )
    install.add_argument(
        "--allow-test-packages",
        action="store_true",
        help='Allow installing apps built with android:testOnly="true"',
    )
    install.add_argument(
        "--user",
        default=None,
        help='Install/uninstall for a specific user id, or "all"/"current" (install only)',
    )
    install.add_argument(
        "--obb",
        nargs="+",
        default=None,
        metavar="OBB_PATH",
        help="Path(s) to OBB expansion file(s) to push alongside the apk(s)",
    )
    install.add_argument(
        "--adb-path", default=None, help="Path to the adb executable (if not in PATH)"
    )
    install.set_defaults(func=_cmd_install)

    uninstall = subparsers.add_parser(
        "uninstall", help="Uninstall a package from connected device(s)"
    )
    uninstall.add_argument("package", help="Package name to uninstall")
    uninstall.add_argument("--device", default=None, help="Target a specific device id")
    uninstall.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep the app's data/cache directories after removal",
    )
    uninstall.add_argument(
        "--user", default=None, help="Uninstall for a specific user id only"
    )
    uninstall.add_argument(
        "--version-code",
        type=int,
        default=None,
        help="Only uninstall if the installed app has this exact versionCode",
    )
    uninstall.add_argument(
        "--adb-path", default=None, help="Path to the adb executable (if not in PATH)"
    )
    uninstall.set_defaults(func=_cmd_uninstall)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
