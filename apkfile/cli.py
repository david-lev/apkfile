import argparse
import os
import shutil
import sys
import tempfile
from typing import Callable, Dict, Union

from apkfile import ApkFile, ApkmFile, XapkFile, ApksFile, __version__, _BaseApkFile, _BaseZipApkFile, install_apks


def main():
    apk_types: Dict[str, Callable[..., _BaseApkFile]] = \
        {'apk': ApkFile, 'xapk': XapkFile, 'apkm': ApkmFile, 'apks': ApksFile}
    parser = argparse.ArgumentParser(
        prog='apkfile',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'file',
        type=lambda f: f if os.path.isfile(f) else parser.error(f'File "{f}" does not exist'),
        help=f'Path to file. Supported types: .{", .".join(apk_types.keys())}'
    )
    parser.add_argument(
        '-t', '--type',
        choices=('auto', *apk_types.keys()),
        default='auto',
        help='Type of apk file. Default: auto, which will try to guess the type from the file extension'
    )
    parser.add_argument('-j', '--json', help='Print info in json format', action='store_true')
    parser.add_argument('--recursive', help='Print info recursively', action='store_false')
    parser.add_argument('--only', help='Only print the specified fields', nargs='+')
    parser.add_argument('--aapt', type=str, help='Path to aapt executable')
    parser.add_argument('-v', '--version', action='version', version=__version__)
    parser.add_argument('-sb', '--skip-broken', help='Skip broken splits', action='store_true')
    parser.add_argument('-o', '--output', type=str, help='Output directory', dest='output')

    subparsers = parser.add_subparsers(dest='action', help='Action to perform', required=False)

    rename_parser = subparsers.add_parser('rename', help='Rename file (e.g. {package_name}-{version_code}.apk)')
    rename_parser.add_argument('new_name', type=str, help='New name for renamed apk file')

    install_parser = subparsers.add_parser('install', help='Install the file')
    install_parser.add_argument(
        '-d', '--devices',
        dest='devices',
        nargs='+',
        help='Devices to install the apk on. If not specified, the apk will be installed on all connected devices'
    )
    install_parser.add_argument(
        '-nc', '--no-check',
        dest='no_check',
        help='Check apk(s) compatibility before installing',
        action='store_true'
    )
    install_parser.add_argument(
        '-r', '--upgrade',
        dest='upgrade',
        help='Upgrade existing apk(s) `INSTALL_FAILED_VERSION_DOWNGRADE`',
        action='store_true'
    )
    install_parser.add_argument(
        '-i', '--installer',
        dest='installer',
        help='Installer package name'
    )
    install_parser.add_argument('--adb', type=str, help='Path to adb executable')
    subparsers.add_parser('extract', help='Extract apks')

    args = parser.parse_args()

    tmp_dir = tempfile.mkdtemp()
    try:
        if args.type == 'auto':
            file_type = args.file.split('.')[-1]
            if file_type not in apk_types:
                print('Unknown file type (use --type XXX to specify file type)')
                sys.exit(1)
            obj = apk_types[file_type]
        else:
            obj = apk_types[args.type]
        obj_args = {'path': args.file, 'aapt_path': args.aapt}
        if issubclass(obj, _BaseZipApkFile):
            obj_args.update({'skip_broken_splits': args.skip_broken, 'extract_path': args.output or tmp_dir})
        apk: Union[ApkFile, _BaseZipApkFile] = obj(**obj_args)

        if args.action is None:
            if args.json:
                import json
                print(json.dumps(apk.as_dict(
                    only=args.only, **({'recursive': args.recursive} if isinstance(apk, _BaseZipApkFile) else {})),
                    indent=4,
                    ensure_ascii=False
                ))
            else:
                print(
                    f"File: {apk.path}",
                    f"App name: {apk.app_name if hasattr(apk, 'app_name') else (apk.labels.get('en', list(apk.labels.values())[0] if apk.labels else 'Unknown'))}",
                    f"Package name: {apk.package_name}",
                    f"Version code: {apk.version_code}",
                    f"Version name: {apk.version_name}",
                    f"Min SDK: {apk.min_sdk_version}",
                    f"Target SDK: {apk.target_sdk_version}",
                    f"Abis: {', '.join(apk.abis) if apk.abis else 'All'}",
                    f"Supported screens: {', '.join(apk.supported_screens) if apk.supported_screens else 'None'}",
                    f"Launchable activity: {apk.launchable_activity}",
                    f"Splits: {', '.join(s.split_name for s in apk.splits) if hasattr(apk, 'splits') else 'None'}",
                    sep='\n'
                )
        elif args.action == 'rename':
            apk.rename(args.new_name)
            print(f"File renamed to '{apk.path}'")
        elif args.action == 'install':
            print(f'Installing {apk.package_name} on {args.devices or "all devices"}: ({apk.size / 1024 / 1024:.2f} MB)')
            res = install_apks(
                apks=apk,
                devices=args.devices,
                skip_broken=args.skip_broken,
                check=not args.no_check,
                adb_path=args.adb,
                aapt_path=args.aapt
            )
            if args.json:
                import json
                print(json.dumps(res, indent=4))
            else:
                for device, device_res in res.items():
                    print(f"[{device}] {', '.join(device_res.keys())}")
        elif args.action == 'extract':
            apk.extract(args.output)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)
    finally:
        shutil.rmtree(tmp_dir)


if __name__ == '__main__':
    main()
