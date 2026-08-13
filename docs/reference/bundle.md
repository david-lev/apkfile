# Bundles: ApkmFile, XapkFile, ApksFile

Each bundle format is a zip archive with a small JSON manifest describing a base apk and any splits.
`base`/`splits` are read lazily, directly out of the archive's bytes — no disk extraction happens for
metadata purposes.

::: apkfile.ApkmFile

::: apkfile.XapkFile

::: apkfile.ApksFile
