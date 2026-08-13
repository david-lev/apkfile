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
from ._bundle import ApkmFile, ApksFile, XapkFile
from .diff import diff as diff_apks
from .install import install_apks

_LOADERS: dict[str, Callable[[str], Any]] = {
    ".apk": ApkFile,
    ".apkm": ApkmFile,
    ".xapk": XapkFile,
    ".apks": ApksFile,
}


def _load(path: str) -> Any:
    suffix = Path(path).suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise SystemExit(
            f"Don't know how to open {path!r} (unrecognized extension {suffix!r})"
        )
    return loader(path)


def _cmd_info(args: argparse.Namespace) -> None:
    apk = _load(args.path)
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
        adb_path=args.adb_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apkfile")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="Print an apk/bundle's metadata as JSON")
    info.add_argument("path", help="Path to a .apk/.apkm/.xapk/.apks file")
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
        "--adb-path", default=None, help="Path to the adb executable (if not in PATH)"
    )
    install.set_defaults(func=_cmd_install)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
