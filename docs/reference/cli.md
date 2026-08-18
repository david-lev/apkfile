# CLI Reference

The `apkfile` console script, installed alongside the library. See [Command-line interface](../quickstart.md#command-line-interface)
in the Quickstart for usage examples. This page is the full `--help` output for every command.

Every subcommand accepts `-v`/`--verbose` (repeatable) to enable apkfile's logging, which is silent by
default (see [`ApkFile`][apkfile.ApkFile]'s module docs on opt-in logging): `-v` shows INFO-level progress,
`-vv` also shows every individual `adb` command.

`install`/`uninstall` always print a one-line outcome regardless of `-v` — e.g. `Installed on 1 device(s):
emulator-5554` — and exit `1` with `Nothing was installed (...)`/`Nothing was uninstalled (...)` on stderr
if no device ended up with anything actually done (no device connected, or none had anything compatible to
install/uninstall — not itself an error, since that's a legitimate outcome across a multi-device run, but
worth surfacing rather than exiting `0` silently). Any of apkfile's own errors (a failed `adb` command, an
invalid apk/bundle, `adb` not found) print a single `Error: ...` line to stderr and exit `1`, instead of a
Python traceback.

```
$ apkfile --help
usage: apkfile [-h] [--version] {info,diff,install,uninstall} ...

positional arguments:
  {info,diff,install,uninstall}
    info                Print an apk/bundle's metadata as JSON
    diff                Print the differences between two apks/bundles as JSON
    install             Install apk(s) to connected device(s)
    uninstall           Uninstall a package from connected device(s)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `apkfile info`

Loads a single `.apk`/`.apkm`/`.xapk`/`.apks`/`.apkv` file and prints its metadata as JSON
(`as_dict()`'s output).

```
$ apkfile info --help
usage: apkfile info [-h] [-v] [--password PASSWORD] path

positional arguments:
  path                 Path to a .apk/.apkm/.xapk/.apks/.apkv file

options:
  -h, --help           show this help message and exit
  -v, --verbose        Increase log verbosity (-v for progress, -vv for every
                       adb command)
  --password PASSWORD  Password for an encrypted .apkv archive
```

## `apkfile diff`

Loads two apks/bundles and prints their [`ApkDiff`][apkfile.ApkDiff] as JSON.

```
$ apkfile diff --help
usage: apkfile diff [-h] [-v] a b

positional arguments:
  a              Path to the baseline .apk/.apkm/.xapk/.apks file
  b              Path to the .apk/.apkm/.xapk/.apks file to compare against a

options:
  -h, --help     show this help message and exit
  -v, --verbose  Increase log verbosity (-v for progress, -vv for every adb
                 command)
```

## `apkfile install`

Installs one or more `.apk` paths (a base apk + its splits), or a single `.apkm`/`.xapk`/`.apks`/`.apkv`
bundle, to connected device(s) — see [`install_apks`][apkfile.install_apks] for the underlying behavior
(device-compatibility checks, multi-split sessions, OBB pushes).

```
$ apkfile install --help
usage: apkfile install [-h] [-v] [--password PASSWORD] [--device DEVICE]
                       [--upgrade] [--no-check] [--skip-broken]
                       [--installer INSTALLER]
                       [--originating-uri ORIGINATING_URI]
                       [--grant-permissions] [--allow-downgrade]
                       [--allow-test-packages] [--user USER]
                       [--obb OBB_PATH [OBB_PATH ...]] [--adb-path ADB_PATH]
                       paths [paths ...]

positional arguments:
  paths                 Path(s) to .apk file(s) (a base apk + its splits), or
                        a single .apkm/.xapk/.apks/.apkv bundle

options:
  -h, --help            show this help message and exit
  -v, --verbose         Increase log verbosity (-v for progress, -vv for every
                        adb command)
  --password PASSWORD   Password for an encrypted .apkv bundle
  --device DEVICE       Target a specific device id
  --upgrade             Upgrade if already installed
  --no-check            Skip device-compatibility checking
  --skip-broken         Skip apks that fail to parse instead of raising (only
                        relevant with --check)
  --installer INSTALLER
                        Package name of the app performing the installation
                        (e.g. com.android.vending)
  --originating-uri ORIGINATING_URI
                        The URI of the app performing the installation
  --grant-permissions   Grant all runtime permissions the app requests at
                        install time
  --allow-downgrade     Allow installing a lower versionCode over an existing
                        install
  --allow-test-packages
                        Allow installing apps built with
                        android:testOnly="true"
  --user USER           Install/uninstall for a specific user id, or
                        "all"/"current" (install only)
  --obb OBB_PATH [OBB_PATH ...]
                        Path(s) to OBB expansion file(s) to push alongside the
                        apk(s)
  --adb-path ADB_PATH   Path to the adb executable (if not in PATH)
```

!!! note
    `--no-check` skips the compatibility gate described in [Installing/Uninstalling](install.md) —
    `min_sdk_version`, ABI (`ro.product.cpu.abilist`), and locale/density-split checks against the
    connected device(s). Installing without it still fails at the `adb`/`pm` level if the device is
    genuinely incompatible (e.g. `INSTALL_FAILED_NO_MATCHING_ABIS`); the check only lets apkfile skip
    that device before spending time pushing files it already knows won't install.

## `apkfile uninstall`

Uninstalls a package from connected device(s) — by package name, or by a path to a
`.apk`/`.apkm`/`.xapk`/`.apks`/`.apkv` file (`apkfile uninstall app.apk` reads the package name out of it,
same as `apkfile info app.apk`'s `package_name` field, without printing anything else).

```
$ apkfile uninstall --help
usage: apkfile uninstall [-h] [-v] [--password PASSWORD] [--device DEVICE]
                         [--keep-data] [--user USER]
                         [--version-code VERSION_CODE] [--adb-path ADB_PATH]
                         package

positional arguments:
  package               Package name to uninstall, or a path to a
                        .apk/.apkm/.xapk/.apks/.apkv file to read the package
                        name from

options:
  -h, --help            show this help message and exit
  -v, --verbose         Increase log verbosity (-v for progress, -vv for every
                        adb command)
  --password PASSWORD   Password for an encrypted .apkv archive (only relevant
                        if package is a path)
  --device DEVICE       Target a specific device id
  --keep-data           Keep the app's data/cache directories after removal
  --user USER           Uninstall for a specific user id only
  --version-code VERSION_CODE
                        Only uninstall if the installed app has this exact
                        versionCode
  --adb-path ADB_PATH   Path to the adb executable (if not in PATH)
```
