from __future__ import annotations

from apkfile import InstallLocation


def test_install_location_defaults_to_internal_only_when_unset() -> None:
    # Per developer.android.com/guide/topics/manifest/manifest-element#install: "internalOnly"
    # is the documented default when `android:installLocation` isn't declared -- NOT "auto".
    assert InstallLocation(None) is InstallLocation.INTERNAL_ONLY


def test_install_location_unrecognized_value_falls_back_to_internal_only() -> None:
    assert InstallLocation("something-weird") is InstallLocation.INTERNAL_ONLY


def test_install_location_equals_plain_string() -> None:
    assert InstallLocation.PREFER_EXTERNAL == "preferExternal"
    assert InstallLocation("auto") is InstallLocation.AUTO
