from __future__ import annotations

from apkfile import ApkFile
from apkfile.diff import diff


def test_diff_against_self_is_empty(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    result = diff(apk, apk)
    assert result.package_name_changed is False
    assert result.version_code_delta == 0
    assert result.size_delta == 0
    assert result.permissions_added == ()
    assert result.permissions_removed == ()
    assert result.signing_changed is False


def test_diff_between_different_apks(
    politedroid_path: str, test_debug_path: str
) -> None:
    a = ApkFile(test_debug_path)
    b = ApkFile(politedroid_path)
    result = diff(a, b)
    assert result.package_name_changed is True
    assert set(result.permissions_added) == {
        "android.permission.READ_CALENDAR",
        "android.permission.RECEIVE_BOOT_COMPLETED",
    }
    assert result.permissions_removed == ()
    assert result.version_name_from == a.version_name
    assert result.version_name_to == b.version_name
    assert result.size_delta == b.size - a.size
    # different, unrelated self-signed certs -> no shared fingerprint.
    assert result.signing_changed is True


def test_apkfile_diff_convenience_method(
    politedroid_path: str, test_debug_path: str
) -> None:
    a = ApkFile(test_debug_path)
    b = ApkFile(politedroid_path)
    assert a.diff(b) == diff(a, b)
