from __future__ import annotations

from apkfile import ApkFile
from apkfile._security import ComponentType, ProtectionLevel


def test_permissions_have_aosp_details(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    permissions = {p.name: p for p in apk.security.permissions}
    assert permissions["android.permission.READ_CALENDAR"].protection_level == (
        ProtectionLevel.DANGEROUS
    )
    assert permissions["android.permission.READ_CALENDAR"].is_dangerous is True
    assert permissions[
        "android.permission.RECEIVE_BOOT_COMPLETED"
    ].protection_level == (ProtectionLevel.NORMAL)
    assert apk.security.dangerous_permissions == ("android.permission.READ_CALENDAR",)


def test_minimal_apk_has_no_permissions(test_debug_path: str) -> None:
    apk = ApkFile(test_debug_path)
    assert apk.security.permissions == ()
    assert apk.security.dangerous_permissions == ()


def test_exported_components_and_unprotected_findings(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    components = {c.name: c for c in apk.security.exported_components}
    assert components["com.politedroid.Preferences"].type == ComponentType.ACTIVITY
    assert components["com.politedroid.Preferences"].exported is True
    assert components["com.politedroid.Preferences"].has_intent_filter is True
    assert components["com.politedroid.Update"].type == ComponentType.RECEIVER
    assert components["com.politedroid.Update"].exported is True

    # neither component declares a `permission`, so both are unprotected findings.
    unprotected_names = {c.name for c in apk.security.unprotected_exported_components}
    assert unprotected_names == set(components)


def test_manifest_flags_default_sensibly(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    security = apk.security
    assert security.debuggable is False
    assert security.allow_backup is True  # unset -> platform default
    assert security.uses_cleartext_traffic is None  # unset in this manifest
    assert security.has_network_security_config is False
    assert security.deep_links == ()


def test_effective_uses_cleartext_traffic_defaults_by_target_sdk(
    politedroid_path: str,
) -> None:
    apk = ApkFile(politedroid_path)
    security = apk.security
    assert security.effective_uses_cleartext_traffic(27) is True
    assert security.effective_uses_cleartext_traffic(28) is False
    assert security.effective_uses_cleartext_traffic(None) is True
