# apkfile

apkfile is a small, fully-typed Python library for reading metadata out of Android `.apk`, `.apkm`,
`.xapk`, and `.apks` files — package/version info, permissions, signing certificates, manifest security
posture (exported components, deep links, dangerous permissions), size/DEX composition, and diffing between
two apks — and for installing them to a connected device via `adb`.

It has no external binary dependency. All parsing (including signing blocks and DEX headers) is done
in-process, most of it via [androguard](https://github.com/androguard/androguard)
(`AndroidManifest.xml` + `resources.arsc` + certificates), not by shelling out to Google's deprecated `aapt`
tool.

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

apk.install(upgrade=True)
```

Continue to the [Quickstart](quickstart.md) for a full walkthrough covering bundles (`.apkm`/`.xapk`/
`.apks`), signing, manifest security, size/DEX composition, diffing two apks, installing over `adb`, and the
`apkfile` CLI — or jump straight to the [API Reference](reference/apk.md) for the details on any class or
function.

## Where things live

- **[`ApkFile`][apkfile.ApkFile]** — a single `.apk`, the core class everything else builds on.
- **[`ApkmFile`][apkfile.ApkmFile] / [`XapkFile`][apkfile.XapkFile] / [`ApksFile`][apkfile.ApksFile]** —
  bundle archive formats: a base apk + splits + a small JSON manifest, read lazily straight out of the
  archive's bytes.
- **`.signing`, `.security`, `.size_breakdown`, `.dex_info`** — computed on first access
  (`functools.cached_property`) from the wrapped apk, on both `ApkFile` and every bundle class.
- **[`diff()`][apkfile.diff] / [`ApkFile.diff`][apkfile.ApkFile.diff]** — compare two apks or bundles.
- **[`install_apks()`][apkfile.install_apks] / `.install()`** — push apk(s) to a connected device via `adb`.

## Source & issues

apkfile is developed on [GitHub](https://github.com/david-lev/apkfile). Bug reports and feature requests are
welcome on the [issue tracker](https://github.com/david-lev/apkfile/issues).
