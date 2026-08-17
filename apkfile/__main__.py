"""The `apkfile` command-line interface."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import loguru

from . import __version__
from ._apk import ApkFile
from ._apkv import ApkvFile
from ._bundle import ApkmFile, ApksFile, XapkFile
from .diff import diff as diff_apks
from .install import install_apks, uninstall_apks

_LOG_FORMAT = (
    "<green>{time:HH:mm:ss}</green> <level>{level: <8}</level> <level>{message}</level>"
)


def _configure_logging(verbosity: int) -> None:
    """Wire up apkfile's logging for CLI use (disabled by default — see `apkfile/__init__.py`).

    `-v` shows INFO-level milestones (e.g. per-device install/uninstall progress); `-vv` also
    shows DEBUG (every individual `adb` command).
    """
    if verbosity <= 0:
        return
    loguru.logger.enable("apkfile")
    loguru.logger.remove()
    loguru.logger.add(
        sys.stderr,
        level="DEBUG" if verbosity >= 2 else "INFO",
        colorize=True,
        format=_LOG_FORMAT,
    )


_LOADERS: dict[str, Callable[..., Any]] = {
    ".apk": ApkFile,
    ".apkm": ApkmFile,
    ".xapk": XapkFile,
    ".apks": ApksFile,
    ".apkv": ApkvFile,
}
# The bundle formats among `_LOADERS` — each wraps a base apk + splits behind its own `.install()`
# (which extracts them to a temp dir first), unlike a bare `.apk` path that `install_apks()` can
# take directly.
_BUNDLE_LOADERS: dict[str, Callable[..., Any]] = {
    k: v for k, v in _LOADERS.items() if k != ".apk"
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
    # A bundle (.apkm/.xapk/.apks/.apkv) is a single archive containing its own base+splits (and,
    # for .xapk, OBBs) — it needs its own `.install()`, which extracts them to a temp dir first,
    # rather than being handed straight to `install_apks()` like a plain .apk path/paths.
    suffix = Path(args.paths[0]).suffix.lower() if len(args.paths) == 1 else None
    bundle_loader = _BUNDLE_LOADERS.get(suffix) if suffix else None
    if bundle_loader is not None:
        loader_kwargs: dict[str, Any] = {"skip_broken_splits": args.skip_broken}
        if suffix == ".apkv":
            loader_kwargs["password"] = args.password
        bundle = bundle_loader(args.paths[0], **loader_kwargs)
        bundle.install(
            check=not args.no_check,
            upgrade=args.upgrade,
            device_id=args.device,
            installer=args.installer,
            originating_uri=args.originating_uri,
            grant_permissions=args.grant_permissions,
            allow_downgrade=args.allow_downgrade,
            allow_test_packages=args.allow_test_packages,
            user=args.user,
            obb_paths=args.obb,
            adb_path=args.adb_path,
        )
        return

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
    # A `parents=[...]` mixin, added to every *subparser* (not the top-level parser — argparse's
    # subparsers action always reparses its remaining args into a fresh namespace and copies that
    # over the outer one, so a same-named attribute set on the top-level parser would just get
    # silently clobbered back to its default; confirmed hands-on), so `-v`/`--verbose` is used as
    # `apkfile install ... -v`, not `apkfile -v install ...`.
    verbose_parent = argparse.ArgumentParser(add_help=False)
    verbose_parent.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v for progress, -vv for every adb command)",
    )

    parser = argparse.ArgumentParser(prog="apkfile")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser(
        "info", help="Print an apk/bundle's metadata as JSON", parents=[verbose_parent]
    )
    info.add_argument("path", help="Path to a .apk/.apkm/.xapk/.apks/.apkv file")
    info.add_argument(
        "--password", default=None, help="Password for an encrypted .apkv archive"
    )
    info.set_defaults(func=_cmd_info)

    diff = subparsers.add_parser(
        "diff",
        help="Print the differences between two apks/bundles as JSON",
        parents=[verbose_parent],
    )
    diff.add_argument("a", help="Path to the baseline .apk/.apkm/.xapk/.apks file")
    diff.add_argument(
        "b", help="Path to the .apk/.apkm/.xapk/.apks file to compare against a"
    )
    diff.set_defaults(func=_cmd_diff)

    install = subparsers.add_parser(
        "install",
        help="Install apk(s) to connected device(s)",
        parents=[verbose_parent],
    )
    install.add_argument(
        "paths",
        nargs="+",
        help="Path(s) to .apk file(s) (a base apk + its splits), or a single "
        ".apkm/.xapk/.apks/.apkv bundle",
    )
    install.add_argument(
        "--password", default=None, help="Password for an encrypted .apkv bundle"
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
        "uninstall",
        help="Uninstall a package from connected device(s)",
        parents=[verbose_parent],
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
    _configure_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
