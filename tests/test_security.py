from __future__ import annotations

from lxml import etree

from apkfile import ApkFile
from apkfile._security import (
    ComponentType,
    ImpliedPermission,
    ProtectionLevel,
    build_security_info,
)

_NS = "{http://schemas.android.com/apk/res/android}"


def _manifest_with_provider(**provider_attrs: str) -> etree._Element:
    root = etree.Element("manifest")
    application = etree.SubElement(root, "application")
    provider = etree.SubElement(application, "provider")
    provider.set(_NS + "name", ".MyProvider")
    for attr, value in provider_attrs.items():
        provider.set(_NS + attr, value)
    return root


def _fake_apk(mocker, *, target_sdk_version: int, package: str = "com.example"):
    apk = mocker.MagicMock()
    apk.get_package.return_value = package
    apk.get_effective_target_sdk_version.return_value = target_sdk_version
    apk.get_permissions.return_value = []
    apk.get_declared_permissions_details.return_value = {}
    apk.get_requested_aosp_permissions_details.return_value = {}
    apk.get_uses_implied_permission_list.return_value = []
    return apk


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


# -- <provider> default-exported + read/writePermission (no real-world .apk fixture has a
# provider, so these build a manifest tree directly with lxml, same as androguard would parse
# a real AndroidManifest.xml into) -------------------------------------------------------------


def test_provider_defaults_to_exported_below_api_17(mocker) -> None:
    manifest_root = _manifest_with_provider()  # no explicit `exported`
    apk = _fake_apk(mocker, target_sdk_version=16)
    (provider,) = build_security_info(apk, manifest_root).exported_components
    assert provider.type == ComponentType.PROVIDER
    assert provider.exported is True


def test_provider_defaults_to_unexported_from_api_17(mocker) -> None:
    manifest_root = _manifest_with_provider()  # no explicit `exported`
    apk = _fake_apk(mocker, target_sdk_version=17)
    (provider,) = build_security_info(apk, manifest_root).exported_components
    assert provider.exported is False
    # not exported at all -> not a candidate for the unprotected-components finding.
    assert build_security_info(apk, manifest_root).unprotected_exported_components == ()


def test_provider_explicit_exported_overrides_target_sdk_default(mocker) -> None:
    manifest_root = _manifest_with_provider(exported="true")
    apk = _fake_apk(mocker, target_sdk_version=34)
    (provider,) = build_security_info(apk, manifest_root).exported_components
    assert provider.exported is True


def test_provider_read_write_permission_are_captured_separately(mocker) -> None:
    manifest_root = _manifest_with_provider(
        exported="true",
        readPermission="com.example.READ",
        writePermission="com.example.WRITE",
    )
    apk = _fake_apk(mocker, target_sdk_version=34)
    (provider,) = build_security_info(apk, manifest_root).exported_components
    assert provider.permission is None
    assert provider.read_permission == "com.example.READ"
    assert provider.write_permission == "com.example.WRITE"
    assert provider.is_permission_protected is True


def test_provider_with_only_read_permission_is_not_flagged_unprotected(mocker) -> None:
    # a provider protected on at least one axis shouldn't show up as a "fully open" finding,
    # even though it has no plain `permission` attribute.
    manifest_root = _manifest_with_provider(
        exported="true", readPermission="com.example.READ"
    )
    apk = _fake_apk(mocker, target_sdk_version=34)
    security = build_security_info(apk, manifest_root)
    assert security.unprotected_exported_components == ()


def test_exported_provider_with_no_permission_at_all_is_unprotected(mocker) -> None:
    manifest_root = _manifest_with_provider(exported="true")
    apk = _fake_apk(mocker, target_sdk_version=34)
    security = build_security_info(apk, manifest_root)
    assert len(security.unprotected_exported_components) == 1
    assert security.unprotected_exported_components[0].type == ComponentType.PROVIDER


def test_non_provider_components_have_no_read_write_permission(
    politedroid_path: str,
) -> None:
    apk = ApkFile(politedroid_path)
    for component in apk.security.exported_components:
        assert component.read_permission is None
        assert component.write_permission is None


def test_implied_permissions_from_legacy_target_sdk(politedroid_path: str) -> None:
    # politedroid.apk has no explicit target_sdk_version, so it resolves (via min_sdk_version=3)
    # to an old effective target sdk, which implies WRITE/READ_EXTERNAL_STORAGE + READ_PHONE_STATE
    # under Android's legacy permission-implication rules.
    apk = ApkFile(politedroid_path)
    implied = {p.name for p in apk.security.implied_permissions}
    assert "android.permission.WRITE_EXTERNAL_STORAGE" in implied
    assert "android.permission.READ_EXTERNAL_STORAGE" in implied
    assert "android.permission.READ_PHONE_STATE" in implied


def test_implied_permissions_field_is_wired_through(mocker) -> None:
    manifest_root = _manifest_with_provider()
    apk = _fake_apk(mocker, target_sdk_version=34)
    apk.get_uses_implied_permission_list.return_value = [
        ("android.permission.READ_CALL_LOG", "15")
    ]
    security = build_security_info(apk, manifest_root)
    assert security.implied_permissions == (
        ImpliedPermission(name="android.permission.READ_CALL_LOG", max_sdk_version=15),
    )
