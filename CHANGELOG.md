# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1]

Documentation-only release (no code changes) — republished so PyPI's project page picks up the refreshed
README.

- Added a logo and a fuller badge row (downloads, tests, coverage, pre-commit.ci, license, code quality) to
  the README.
- Trimmed the top-of-README description down to what the library does, moving the implementation detail
  (androguard, no external binary) into the existing "How this library works" section further down.

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
- `ApkFile.path` (and every bundle's `.path`) is a `pathlib.Path`, not a `str`. Comparisons against a bare
  string (`apk.path == "/some/path"`) no longer match — compare against `Path("/some/path")`, or use
  `str(apk.path)`.
- `ApkFile.icons` is `tuple[Icon, ...]` (was `dict[int, str]`). Each `Icon` has `.density`, `.bucket` (a
  `DensityBucket`), `.path`, and `.read_bytes()`/`.extract(path)` methods. It's also more complete: the
  previous implementation missed `anydpi` (adaptive icon) and `nodpi` variants entirely. Use
  `apk.best_icon(max_dpi=...)` to pick a single icon.
- `ApkFile.supported_screens` is `tuple[ScreenSize, ...]` (was `tuple[str, ...]`).
- `Abi.is_compatible_with()` no longer claims `x86`/`x86_64` devices can run `arm`/`arm64` code — stock
  Android has no built-in ARM↔x86 translation layer, so the previous behavior was simply wrong and could
  have caused `install_apks()` to push an incompatible native-code split onto an x86 device/emulator.
- `InstallLocation`'s default (when `android:installLocation` isn't declared) is `INTERNAL_ONLY`, per
  [the docs](https://developer.android.com/guide/topics/manifest/manifest-element#install) — it was
  previously (incorrectly) reported as `AUTO`.
- A `<provider>`'s default `exported` value is now resolved correctly: it depends on `targetSdkVersion`
  (`True` up to API 16, `False` from API 17), unlike activities/services/receivers, whose default instead
  depends on whether they declare an `<intent-filter>`.

### Added

- A minimal `apkfile` CLI: `apkfile info <path>` prints an APK/bundle's metadata as JSON; `apkfile diff <a>
  <b>` prints the differences between two apks/bundles as JSON; `apkfile install <path...>` installs to
  connected device(s) (`--upgrade`/`--installer`/`--originating-uri`/`--adb-path`/`--skip-broken`).
- `ApkFile.signing` (`SigningInfo`): signing scheme(s) (`v1`/`v2`/`v3`/`v3.1`) and certificate(s)
  (`Certificate` — subject/issuer, canonical (Java-`X500Principal`-compatible) subject/issuer, fingerprints,
  validity, public key algorithm/bit size, debug-cert and self-signed detection, expiry check), plus
  `has_duplicate_signature_ids` (a tamper/verifier-confusion smell).
- `ApkFile.security` (`SecurityInfo`): requested permissions with AOSP protection levels
  (`PermissionInfo`/`ProtectionLevel`) and a `dangerous_permissions` shortcut, permissions Android implies
  without the app declaring them (`implied_permissions`), exported activity/service/receiver/provider status
  (`ExportedComponent`, including provider `read_permission`/`write_permission`) with an
  `unprotected_exported_components` finding, deep links resolved from `VIEW` intent filters (`DeepLink`), and
  `debuggable`/`allow_backup`/`uses_cleartext_traffic`/`has_network_security_config`.
- `ApkFile.size_breakdown` (`SizeBreakdown`): on-disk size broken down by dex/resources/native
  libs/assets/manifest/signing/other. `ApkFile.dex_info` (`DexInfo`): method/class/string counts across
  `classesN.dex`, read directly off each dex's header (no full bytecode analysis).
- `ApkFile.diff(other)` / `apkfile.diff.diff(a, b)` (`ApkDiff`): permission/feature/library/ABI/locale
  deltas, version/size/SDK deltas, and `signing_changed`, between two apks (or bundles).
- `ApkFile.max_sdk_version` and `ApkFile.form_factors` (`FormFactor.TV`/`WEARABLE`, from Android's own
  TV/wearable manifest heuristics).
- `.signing`/`.security` (delegate to the base apk) and `.size_breakdown`/`.dex_info` (summed across base +
  every split) are available on `ApkmFile`/`XapkFile`/`ApksFile` too, alongside the existing
  `max_sdk_version`/`form_factors`/`supported_screens` delegation.
- Full type hints and a `py.typed` marker (PEP 561).
- A test suite (`pytest`, 116 tests).

## [0.1.6] and earlier

See the [GitHub releases](https://github.com/david-lev/apkfile/releases) for the pre-1.0 (aapt-based) history.
