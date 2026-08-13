# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0]

### Breaking changes

- **Removed the `aapt` dependency entirely.** APK parsing is now done in-process with
  [`androguard`](https://github.com/androguard/androguard) — no external binary needs to be installed anymore.
  Every `aapt_path` constructor/method parameter has been removed, as has the `get_raw_aapt()` function.
- Removed `extract_path`, `delete_extracted_files()`, and the `__enter__`/`__exit__` context manager from
  `ApkmFile`/`XapkFile`/`ApksFile`. Bundle files no longer extract to a temporary directory just to read
  metadata — `base`/`splits` are parsed directly from the archive's bytes in memory. `.install()` still
  extracts to a temporary directory internally, but cleans up automatically.
- `ApkFile` instances obtained from a bundle's `base`/`splits` may have `path is None` until you call
  `.save(path)` on them (they haven't been written to disk). `.rename()` raises `ApkFileError` if called
  before `.save()`.
- `icons` now reflects the exact density buckets an app ships icons for (resolved from the real
  `android:icon` resource id), instead of guessed/duplicated density buckets.
- Exceptions are now a proper hierarchy under `ApkFileError` (`InvalidApkError`, `InvalidBundleError`,
  `AdbError`, `AdbNotFoundError`) instead of repurposed builtins (`FileExistsError`/`RuntimeError`).
- `Abi`, `InstallLocation`, and `SplitType` are now `str` enums — comparisons against plain strings
  (`apk.install_location == "auto"`) still work, but code relying on the old custom `__repr__`/hashing
  behavior of a bare `Enum` may need adjusting.
- Minimum supported Python version is now 3.10.

### Added

- A minimal `apkfile` CLI: `apkfile info <path>` prints an APK/bundle's metadata as JSON; `apkfile install
  <path...>` installs to connected device(s).
- Full type hints and a `py.typed` marker (PEP 561).
- A test suite (`pytest`).

## [0.1.6] and earlier

See the [GitHub releases](https://github.com/david-lev/apkfile/releases) for the pre-1.0 (aapt-based) history.
