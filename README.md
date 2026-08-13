<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/david-lev/apkfile/main/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/david-lev/apkfile/main/assets/logo-light.svg" width="96" alt="apkfile logo">
  </picture>
</p>

## [apkfile](https://github.com/david-lev/apkfile) • Python library for handling APK, APKM, XAPK, and APKS files

<p align="center">
  <a href="https://pypi.org/project/apkfile/"><img src="https://img.shields.io/pypi/v/apkfile?color=%2334D058&label=pypi" alt="PyPI Version"/></a>
  <a href="https://pepy.tech/project/apkfile"><img src="https://static.pepy.tech/badge/apkfile" alt="Downloads"/></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%2B-3776ab?color=%2334D058" alt="Python Versions"/></a>
  <a href="https://github.com/david-lev/apkfile/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/david-lev/apkfile/tests.yml?label=tests" alt="Tests"/></a>
  <a href="https://results.pre-commit.ci/latest/github/david-lev/apkfile/main"><img src="https://results.pre-commit.ci/badge/github/david-lev/apkfile/main.svg" alt="pre-commit.ci status"/></a>
  <a href="https://codecov.io/gh/david-lev/apkfile"><img src="https://codecov.io/gh/david-lev/apkfile/graph/badge.svg" alt="Coverage"/></a>
  <a href="https://github.com/david-lev/apkfile/blob/main/LICENSE"><img src="https://img.shields.io/github/license/david-lev/apkfile?color=%2334D058" alt="License"/></a>
  <a href="https://www.codefactor.io/repository/github/david-lev/apkfile/overview/main"><img src="https://www.codefactor.io/repository/github/david-lev/apkfile/badge/main" alt="Code Quality"/></a>
</p>

apkfile reads metadata out of Android `.apk`, `.apkm`, `.xapk`, and `.apks` files — package name, version,
permissions, supported ABIs/languages/densities, icons, signing certificates, manifest security posture
(exported components, deep links, dangerous permissions), size/DEX composition, and more — and can install
them to a connected device over `adb`, or diff two apks against each other. **No external binary is
required**: parsing is done in-process with [androguard](https://github.com/androguard/androguard), not by
shelling out to Google's deprecated `aapt` tool.

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

# Signing certificates, manifest security posture, size/DEX composition
print(apk.signing.is_debug_signed, [c.sha256 for c in apk.signing.all_certificates])
print(apk.security.dangerous_permissions, apk.security.unprotected_exported_components)
print(apk.size_breakdown, apk.dex_info)

# Diff two apks (e.g. two versions of the same app)
old, new = ApkFile("wa-1.apk"), ApkFile("wa-2.apk")
result = old.diff(new)
print(result.permissions_added, result.size_delta, result.signing_changed)

# A quick manifest security report
for component in apk.security.unprotected_exported_components:
    print(
        f"{component.type.value} {component.name} is exported with no permission required"
    )
for name in apk.security.dangerous_permissions:
    print(f"requests dangerous permission: {name}")

# Check whether a split apk can run on a given device ABI
from apkfile import Abi

device_abi = Abi.ARM64
print(all(device_abi.is_compatible_with(a) for a in apk.abis))

# Icons are objects, not just paths -- pick one and extract it
icon = apk.best_icon(max_dpi=320)
icon.extract("icon.png")  # or icon.read_bytes()
print(icon.density, icon.bucket)  # e.g. 320 DensityBucket.XHDPI

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
apkfile info app.apk              # print an apk/bundle's metadata as JSON
apkfile diff old.apk new.apk      # print the differences between two apks/bundles as JSON
apkfile install app.apk           # install to connected device(s)
apkfile install app.apk --upgrade --installer com.android.vending --adb-path /path/to/adb
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

### Migrating from 1.0

- `ApkFile.path` (and every bundle's `.path`) is now a `pathlib.Path`, not a `str`. Comparisons against a
  bare string (`apk.path == "/some/path"`) no longer match — compare against `Path("/some/path")`, or use
  `str(apk.path)`.
- New: `.signing` (`SigningInfo` — signing scheme(s) + certificate(s)), `.security` (`SecurityInfo` —
  permissions with AOSP protection levels, exported components, deep links, `debuggable`/`allowBackup`/
  cleartext-traffic flags), `.size_breakdown` (`SizeBreakdown` — size by dex/resources/native
  libs/assets/...), `.dex_info` (`DexInfo` — method/class/string counts), and `.diff(other)` /
  `apkfile.diff.diff(a, b)` for comparing two apks. All available on `ApkFile` and every bundle class (bundle
  `.signing`/`.security` delegate to the base apk; `.size_breakdown`/`.dex_info` sum base + splits).
- Two behavior-affecting bug fixes, verified against the official Android manifest/NDK docs:
  - `Abi.is_compatible_with()` no longer claims `x86`/`x86_64` devices can run `arm`/`arm64` code — stock
    Android has no built-in ARM↔x86 translation layer, so that was always wrong and could have caused
    `install_apks()` to push an incompatible native-code split onto an x86 emulator.
  - `InstallLocation`'s default (when `android:installLocation` isn't declared) is now `INTERNAL_ONLY`, per
    [the docs](https://developer.android.com/guide/topics/manifest/manifest-element#install) — it was
    previously (incorrectly) reported as `AUTO`.
- `ExportedComponent` gained `read_permission`/`write_permission` (for `<provider>`'s `android:readPermission`
  /`android:writePermission`), and a provider's default `exported` value is now resolved correctly — it
  depends on `targetSdkVersion` (`True` up to API 16, `False` from API 17), unlike activities/services/
  receivers, whose default instead depends on whether they declare an `<intent-filter>`.
- `ApkFile.icons` is now `tuple[Icon, ...]` (was `dict[int, str]`) — each `Icon` has `.density`, `.bucket`
  (a `DensityBucket`), `.path`, and self-serving `.read_bytes()`/`.extract(path)` methods. It's also complete
  now: the old implementation missed `anydpi` (adaptive icon) and `nodpi` variants entirely. Use
  `apk.best_icon(max_dpi=...)` to pick a single icon the way `androguard`/Android itself would.
  `ApkFile.supported_screens` is now `tuple[ScreenSize, ...]` (was `tuple[str, ...]`).
- New fields: `max_sdk_version`, `form_factors` (`tuple[FormFactor, ...]` — TV/wearable heuristics),
  `SecurityInfo.implied_permissions` (permissions Android silently grants under legacy compatibility rules),
  and on `Certificate`: `public_key_algorithm`/`public_key_bit_size`, `canonical_subject`/`canonical_issuer`
  (Java-`X500Principal`-compatible identity strings, safe for comparison unlike `subject`/`issuer`), and on
  `SigningInfo`: `has_duplicate_signature_ids` (a tamper/verifier-confusion smell).

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
