from __future__ import annotations

import json

import pytest

from apkfile.__main__ import main


def test_cli_info_prints_json(capsys, politedroid_path: str) -> None:
    main(["info", politedroid_path])
    out = json.loads(capsys.readouterr().out)
    assert out["package_name"] == "com.politedroid"
    assert out["signing"]["schemes"] == ["v1"]


def test_cli_diff_prints_json(
    capsys, politedroid_path: str, test_debug_path: str
) -> None:
    main(["diff", test_debug_path, politedroid_path])
    out = json.loads(capsys.readouterr().out)
    assert out["package_name_changed"] is True
    assert "android.permission.READ_CALENDAR" in out["permissions_added"]


def test_cli_unknown_extension_raises_systemexit(tmp_path) -> None:
    bogus = tmp_path / "app.aab"
    bogus.write_bytes(b"whatever")
    with pytest.raises(SystemExit):
        main(["info", str(bogus)])


def test_cli_install_passes_all_flags_through(
    mocker, politedroid_path: str, tmp_path
) -> None:
    mock_install = mocker.patch("apkfile.__main__.install_apks")
    obb = tmp_path / "main.1.com.politedroid.obb"
    obb.write_bytes(b"obb-data")
    main(
        [
            "install",
            politedroid_path,
            "--device",
            "emulator-5554",
            "--upgrade",
            "--no-check",
            "--skip-broken",
            "--installer",
            "com.android.vending",
            "--originating-uri",
            "https://example.com",
            "--grant-permissions",
            "--allow-downgrade",
            "--allow-test-packages",
            "--user",
            "all",
            "--obb",
            str(obb),
            "--adb-path",
            "/opt/adb",
        ]
    )
    mock_install.assert_called_once_with(
        apks=[politedroid_path],
        check=False,
        upgrade=True,
        device_id="emulator-5554",
        skip_broken=True,
        installer="com.android.vending",
        originating_uri="https://example.com",
        grant_permissions=True,
        allow_downgrade=True,
        allow_test_packages=True,
        user="all",
        obb_paths=[str(obb)],
        adb_path="/opt/adb",
    )


def test_cli_install_defaults(mocker, politedroid_path: str) -> None:
    mock_install = mocker.patch("apkfile.__main__.install_apks")
    main(["install", politedroid_path])
    mock_install.assert_called_once_with(
        apks=[politedroid_path],
        check=True,
        upgrade=False,
        device_id=None,
        skip_broken=False,
        installer=None,
        originating_uri=None,
        grant_permissions=False,
        allow_downgrade=False,
        allow_test_packages=False,
        user=None,
        obb_paths=None,
        adb_path=None,
    )


def test_cli_uninstall_passes_all_flags_through(mocker) -> None:
    mock_uninstall = mocker.patch("apkfile.__main__.uninstall_apks")
    main(
        [
            "uninstall",
            "com.politedroid",
            "--device",
            "emulator-5554",
            "--keep-data",
            "--user",
            "10",
            "--version-code",
            "4",
            "--adb-path",
            "/opt/adb",
        ]
    )
    mock_uninstall.assert_called_once_with(
        "com.politedroid",
        device_id="emulator-5554",
        keep_data=True,
        user="10",
        version_code=4,
        adb_path="/opt/adb",
    )


def test_cli_uninstall_defaults(mocker) -> None:
    mock_uninstall = mocker.patch("apkfile.__main__.uninstall_apks")
    main(["uninstall", "com.politedroid"])
    mock_uninstall.assert_called_once_with(
        "com.politedroid",
        device_id=None,
        keep_data=False,
        user=None,
        version_code=None,
        adb_path=None,
    )


def test_cli_info_apkv_requires_password(make_apkv) -> None:
    from apkfile.exceptions import EncryptedBundleError

    path = make_apkv(encrypted=True, password="hunter2")
    with pytest.raises(EncryptedBundleError):
        main(["info", path])


def test_cli_info_apkv_plain(capsys, make_apkv) -> None:
    path = make_apkv()
    main(["info", path])
    out = json.loads(capsys.readouterr().out)
    assert out["package_name"] == "com.politedroid"


def test_cli_info_apkv_encrypted_with_password(capsys, make_apkv) -> None:
    path = make_apkv(encrypted=True, password="hunter2")
    main(["info", path, "--password", "hunter2"])
    out = json.loads(capsys.readouterr().out)
    assert out["package_name"] == "com.politedroid"
