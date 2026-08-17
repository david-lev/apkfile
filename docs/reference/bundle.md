# Bundles: ApkmFile, XapkFile, ApksFile, ApkvFile

Each bundle format is a zip archive with a small JSON manifest describing a base apk and any splits.
`base`/`splits` are read lazily, directly out of the archive's bytes — no disk extraction happens for
metadata purposes. [`ApkvFile`][apkfile.ApkvFile] additionally supports an optional password-encrypted
layout (see the [APKv spec](https://github.com/vinstall/apkv-spec)).

::: apkfile.ApkmFile

::: apkfile.XapkFile

::: apkfile.ApksFile

::: apkfile.ApkvFile

::: apkfile.ObbFile
