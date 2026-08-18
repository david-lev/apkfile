# Quickstart

## Reading a single apk

[`ApkFile`][apkfile.ApkFile] wraps a single `.apk`. Every metadata field is a
`functools.cached_property`, computed from the manifest/resource table on first access — nothing beyond
opening the file happens at construction time.

```python
from apkfile import ApkFile

apk = ApkFile("/home/david/Downloads/wa.apk")
print(apk.package_name, apk.version_name, apk.version_code)
print(apk.permissions, apk.abis, apk.langs)
print(apk.as_dict())  # everything, as a JSON-serializable dict
```

### Icons

Icons are objects, not just paths — pick one and extract it, or read its bytes directly:

```python
icon = apk.best_icon(max_dpi=320)
icon.extract("icon.png")  # or: icon.read_bytes()
print(icon.density, icon.bucket)  # e.g. 320 DensityBucket.XHDPI
```

### ABI compatibility

```python
from apkfile import Abi

device_abi = Abi.ARM64
print(all(device_abi.is_compatible_with(a) for a in apk.abis))
```

## Bundle formats: `.apkm` / `.xapk` / `.apks`

[`ApkmFile`][apkfile.ApkmFile], [`XapkFile`][apkfile.XapkFile], and [`ApksFile`][apkfile.ApksFile] each wrap
a zip archive containing a base apk, its splits, and a small JSON manifest. Basic metadata
(`package_name`, `version_code`, ...) comes straight from that manifest, eagerly. `base` and `splits` are
read **lazily, directly out of the archive's bytes** the first time you access them — no disk extraction
happens just to read metadata, so `ApkFile` instances obtained this way have `path is None` until you call
`.save(path)` on them.

```python
from apkfile import ApkmFile, XapkFile, ApksFile

apkm = ApkmFile("/home/david/Downloads/chrome.apkm")
for split in apkm.splits:
    print(split.split_name, split.split_type)

xapk = XapkFile("/home/david/Downloads/telegram.xapk")
print(xapk.abis, xapk.permissions, xapk.langs)

apks = ApksFile("/home/david/Downloads/facebook.apks")
print(apks.base.permissions, apks.md5, apks.sha256)
```

Every bundle class also exposes `.signing`, `.security`, `.size_breakdown`, `.dex_info`, `.diff()`,
`.install()`, and `.as_dict()` — `.signing`/`.security` delegate to the base apk, and
`.size_breakdown`/`.dex_info` sum across the base and every split. See the
[bundle reference](reference/bundle.md) for the full attribute list.

## Signing

[`ApkFile.signing`][apkfile.ApkFile.signing] probes every signing scheme (v1–v3.1) and returns the
certificate(s) recorded under each:

```python
signing = apk.signing
print(signing.schemes, signing.is_debug_signed)
print([cert.sha256 for cert in signing.all_certificates])
print(signing.has_duplicate_signature_ids)  # a tamper/verifier-confusion smell
```

Each [`Certificate`][apkfile.Certificate] carries fingerprints (`sha1`/`sha256`/`md5`), validity dates,
public key info, and both the raw and Java-`X500Principal`-canonicalized subject/issuer (the canonical form
is what's safe to compare for identity — see `Certificate.canonical_subject`).

## Manifest security posture

[`ApkFile.security`][apkfile.ApkFile.security] surfaces the manifest details most relevant to a security
review: dangerous permissions, exported components with no permission guarding them, deep links, and
cleartext-traffic posture.

```python
security = apk.security
print(security.dangerous_permissions)
print(security.unprotected_exported_components)

for component in security.unprotected_exported_components:
    print(
        f"{component.type.value} {component.name} is exported with no permission required"
    )

for name in security.dangerous_permissions:
    print(f"requests dangerous permission: {name}")

print(security.effective_uses_cleartext_traffic(apk.target_sdk_version))
```

## Size & DEX composition

```python
print(apk.size_breakdown)  # dex/resources/native_libs/assets/manifest/signing, in bytes
print(
    apk.dex_info
)  # method_count/class_count/string_count across all classesN.dex files
```

`DexInfo` is read directly off each dex's fixed-offset header with `struct` — deliberately bypassing
androguard's much heavier bytecode-analysis machinery, since only counts are needed.

## Diffing two apks

```python
old, new = ApkFile("wa-1.apk"), ApkFile("wa-2.apk")
result = old.diff(new)
print(result.permissions_added, result.size_delta, result.signing_changed)
```

`ApkFile.diff()` is a thin wrapper over [`apkfile.diff()`][apkfile.diff], which also works on bundle
instances (they're duck-typed against the same attribute names).

## Installing to a device

```python
apk.install(upgrade=True)

# or the standalone function, e.g. for a base apk + splits:
from apkfile import install_apks

install_apks(["base.apk", "config.en.apk", "config.xxhdpi.apk"], upgrade=True)
```

By default, `install()`/`install_apks()` check `min_sdk_version`, ABI, and locale/density-split
compatibility against the connected device(s) before installing. Installing extracts only what's needed
into a temporary directory for the duration of the `adb push`, and cleans up automatically afterwards. You
need [adb](https://developer.android.com/studio/command-line/adb) on `PATH`, or pass `adb_path=` explicitly.

## Command-line interface

```bash
apkfile info app.apk              # print an apk/bundle's metadata as JSON
apkfile diff old.apk new.apk      # print the differences between two apks/bundles as JSON
apkfile install app.apk           # install to connected device(s)
apkfile install app.apk --upgrade --installer com.android.vending --adb-path /path/to/adb
apkfile uninstall com.example.app # uninstall from connected device(s)
apkfile uninstall app.apk         # ...or by apk/bundle path, reading its package name
```

See the [CLI Reference](reference/cli.md) for every command's full `--help` output.
