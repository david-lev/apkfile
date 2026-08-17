# apkfile

apkfile reads metadata out of Android `.apk`, `.apkm`, `.xapk`, `.apks`, and `.apkv` files — package name,
version, permissions, supported ABIs/languages/densities, icons, signing certificates, manifest security
posture (exported components, deep links, dangerous permissions), size/DEX composition, OBB expansion files,
and more — and can install/uninstall them on a connected device over `adb`, or diff two apks against each
other.

It has no external binary dependency. All parsing (including signing blocks, DEX headers, and `.apkv`'s
optional AES-256-CBC encryption layer) is done in-process, most of it via
[androguard](https://github.com/androguard/androguard) (`AndroidManifest.xml` + `resources.arsc` +
certificates), not by shelling out to Google's deprecated `aapt` tool.

## Install

```bash
pip install -U apkfile
# or
uv add apkfile
```

## A quick taste

```python
from apkfile import ApkFile

apk = ApkFile("/home/david/Downloads/wa.apk")
print(apk.package_name, apk.version_name, apk.version_code)
print(apk.signing.is_debug_signed, apk.security.dangerous_permissions)
print(apk.size_breakdown, apk.dex_info)

apk.install(upgrade=True)  # installs to every connected device, in parallel
apk.uninstall()
```

Continue to the [Quickstart](quickstart.md) for a full walkthrough covering bundles (`.apkm`/`.xapk`/
`.apks`/`.apkv`), OBB expansion files, signing, manifest security, size/DEX composition, diffing two apks,
installing/uninstalling over `adb`, and the `apkfile` CLI — or jump straight to the
[API Reference](reference/apk.md) for the details on any class or function.

## Where things live

- **[`ApkFile`][apkfile.ApkFile]** — a single `.apk`, the core class everything else builds on.
- **[`ApkmFile`][apkfile.ApkmFile] / [`XapkFile`][apkfile.XapkFile] / [`ApksFile`][apkfile.ApksFile] /
  [`ApkvFile`][apkfile.ApkvFile]** — bundle archive formats: a base apk + splits + a small JSON manifest
  (`ApkvFile` optionally password-encrypted), read lazily straight out of the archive's bytes.
- **`.signing`, `.security`, `.size_breakdown`, `.dex_info`** — computed on first access
  (`functools.cached_property`) from the wrapped apk, on both `ApkFile` and every bundle class.
- **[`ObbFile`][apkfile.ObbFile]** — OBB expansion file metadata bundled inside a `.xapk`
  (`XapkFile.obb_files`).
- **[`diff()`][apkfile.diff] / [`ApkFile.diff`][apkfile.ApkFile.diff]** — compare two apks or bundles.
- **[`install_apks()`][apkfile.install_apks] / `.install()`** — push apk(s) to a connected device via `adb`,
  in parallel across every connected device.
- **[`uninstall_apks()`][apkfile.uninstall_apks] / `.uninstall()`** — remove a package from a connected
  device, same parallel multi-device behavior as installing.

## Source & issues

apkfile is developed on [GitHub](https://github.com/david-lev/apkfile). Bug reports and feature requests are
welcome on the [issue tracker](https://github.com/david-lev/apkfile/issues).
