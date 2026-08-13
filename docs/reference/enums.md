# Enums

Small `str`-subclassed enums used across apkfile — they compare/hash/serialize like plain strings, so
comparisons against a bare string (e.g. `apk.install_location == "auto"`) still work.

::: apkfile.Abi

::: apkfile.FormFactor

::: apkfile.InstallLocation

::: apkfile.SplitType
