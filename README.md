## ⛏️ [apkfile](https://github.com/david-lev/apkfile) • Python library for handling APK, APKM, XAPK, and APKS files

[![CodeFactor](https://www.codefactor.io/repository/github/david-lev/apkfile/badge)](https://www.codefactor.io/repository/github/david-lev/apkfile)
[![PyPI Downloads](https://img.shields.io/pypi/dm/apkfile?style=flat-square)](https://badge.fury.io/py/apkfile)
[![PyPI Version](https://badge.fury.io/py/apkfile.svg)](https://pypi.org/project/apkfile/)

apkfile reads metadata out of Android `.apk`, `.apkm`, `.xapk`, and `.apks` files — package name, version,
permissions, supported ABIs/languages/densities, icons, and more — and can install them to a connected device
over `adb`. **No external binary is required**: parsing is done in-process with
[androguard](https://github.com/androguard/androguard), not by shelling out to Google's deprecated `aapt`
tool.

### Install

```bash
pip install -U apkfile
# or
uv add apkfile
```

### Usage

```python
from apkfile import ApkFile, XapkFile, ApkmFile, ApksFile

# Get apk info
apk = ApkFile("/home/david/Downloads/wa.apk")
print(apk.package_name, apk.version_name, apk.version_code)
print(apk.as_dict())

# Get apkm info — base/splits are read lazily, straight out of the archive
apkm = ApkmFile("/home/david/Downloads/chrome.apkm")
for split in apkm.splits:
    print(split.split_name, split.split_type)
apkm.install(check=True, upgrade=True)

# Get xapk info
xapk = XapkFile("/home/david/Downloads/telegram.xapk")
print(xapk.abis, xapk.permissions, xapk.langs)

# Get apks info
apks = ApksFile("/home/david/Downloads/facebook.apks")
print(apks.base.permissions, apks.md5, apks.sha256)
```

### CLI

```bash
apkfile info app.apk          # print an apk/bundle's metadata as JSON
apkfile install app.apk       # install to connected device(s)
```

### How this library works

apkfile parses `AndroidManifest.xml` and `resources.arsc` directly, using
[androguard](https://github.com/androguard/androguard) — a pure-Python library, so there's nothing to
install beyond apkfile itself.

- For the archive formats (`.apkm`, `.xapk`, `.apks`), basic info (`package_name`, `version_name`,
  `version_code`, ...) comes from the archive's own JSON manifest. Everything else (`base`, `splits`,
  permissions, languages, ABIs, ...) is parsed **lazily, directly from the archive's bytes** the first time
  you access it — no disk extraction happens just to read metadata. `ApkFile` objects obtained this way have
  `path is None` until you call `.save(path)` on them.
- The library can also install files (optionally checking compatibility first: `min_sdk_version`, `abis`,
  and `langs`/densities for split apks) using [adb](#install-adb) — connect a device and call `.install()`,
  or use the standalone `install_apks()` function directly. Installing extracts only what's needed into a
  temporary directory for the duration of the push, and cleans up automatically afterwards.

### Install adb

If you want to use `.install()`, you need [adb](https://developer.android.com/studio/command-line/adb).

- You can manually provide a path to `adb`: `apk.install(adb_path="/path/to/adb")`.

### Migrating from 0.x

apkfile 1.0 is a from-scratch rewrite. The highlights:

- `aapt` is gone. Every `aapt_path` parameter has been removed, as has `get_raw_aapt()`.
- `extract_path`, `delete_extracted_files()`, and the `with XapkFile(...) as xf:` context-manager pattern
  are gone — reading metadata never touches disk anymore, so there's nothing to clean up. `.install()` still
  uses a temporary directory, but manages it internally.
- Exceptions are now a proper hierarchy under `apkfile.ApkFileError` (`InvalidApkError`,
  `InvalidBundleError`, `AdbError`, `AdbNotFoundError`) instead of repurposed builtins.
- `Abi`, `InstallLocation`, and `SplitType` are `str` enums now — comparisons against plain strings
  (`apk.install_location == "auto"`) still work.
- Minimum supported Python version is 3.10.

See [CHANGELOG.md](CHANGELOG.md) for the full list.
