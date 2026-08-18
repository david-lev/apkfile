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


def test_cli_uninstall_by_apk_path_resolves_package_name(
    mocker, politedroid_path: str
) -> None:
    mock_uninstall = mocker.patch("apkfile.__main__.uninstall_apks")
    main(["uninstall", politedroid_path])
    assert mock_uninstall.call_args.args[0] == "com.politedroid"


def test_cli_uninstall_by_bundle_path_resolves_package_name(mocker, make_apkm) -> None:
    mock_uninstall = mocker.patch("apkfile.__main__.uninstall_apks")
    path = make_apkm()
    main(["uninstall", path])
    assert mock_uninstall.call_args.args[0] == "com.politedroid"


def test_cli_uninstall_by_encrypted_apkv_path_uses_password(mocker, make_apkv) -> None:
    mock_uninstall = mocker.patch("apkfile.__main__.uninstall_apks")
    path = make_apkv(encrypted=True, password="hunter2")
    main(["uninstall", path, "--password", "hunter2"])
    assert mock_uninstall.call_args.args[0] == "com.politedroid"


def test_cli_uninstall_by_apk_path_still_passes_other_flags_through(
    mocker, politedroid_path: str
) -> None:
    mock_uninstall = mocker.patch("apkfile.__main__.uninstall_apks")
    main(["uninstall", politedroid_path, "--device", "emulator-5554", "--keep-data"])
    mock_uninstall.assert_called_once_with(
        "com.politedroid",
        device_id="emulator-5554",
        keep_data=True,
        user=None,
        version_code=None,
        adb_path=None,
    )


def test_cli_info_apkv_requires_password(capsys, make_apkv) -> None:
    path = make_apkv(encrypted=True, password="hunter2")
    with pytest.raises(SystemExit) as excinfo:
        main(["info", path])
    assert excinfo.value.code == 1
    assert "password" in capsys.readouterr().err.lower()


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


def test_cli_install_apkm_bundle_extracts_base_and_splits(mocker, make_apkm) -> None:
    # Regression test: `install` used to hand bundle paths straight to `install_apks()`, which
    # only understands raw .apk files, so a .apkm/.xapk/.apks/.apkv would fail with
    # InvalidApkError instead of installing its base + splits.
    mock_install = mocker.patch("apkfile.install.install_apks")
    path = make_apkm(with_split=True)

    main(["install", path, "--upgrade"])

    assert mock_install.call_count == 1
    kwargs = mock_install.call_args.kwargs
    assert kwargs["upgrade"] is True
    assert len(kwargs["apks"]) == 2  # base + 1 split


def test_cli_install_apkv_encrypted_bundle_passes_password(mocker, make_apkv) -> None:
    mock_install = mocker.patch("apkfile.install.install_apks")
    path = make_apkv(encrypted=True, password="hunter2")

    main(["install", path, "--password", "hunter2"])

    assert mock_install.call_count == 1


def test_cli_install_multiple_apk_paths_still_uses_install_apks(
    mocker, politedroid_path: str
) -> None:
    # A base + split(s) passed as separate .apk paths should still go through install_apks()
    # directly, not be mistaken for a single-file bundle.
    mock_install = mocker.patch("apkfile.__main__.install_apks")

    main(["install", politedroid_path, politedroid_path])

    mock_install.assert_called_once()
    assert mock_install.call_args.kwargs["apks"] == [politedroid_path, politedroid_path]


def test_cli_install_prints_confirmation_on_success(
    capsys, mocker, politedroid_path: str
) -> None:
    mocker.patch("apkfile.__main__.install_apks", return_value=("emulator-5554",))
    main(["install", politedroid_path])
    out = capsys.readouterr().out
    assert "emulator-5554" in out
    assert "Installed" in out


def test_cli_install_nothing_installed_exits_nonzero(
    capsys, mocker, politedroid_path: str
) -> None:
    # Nothing raised (no AdbError), but no device had anything compatible to install — without
    # this, the CLI used to exit 0 and print nothing at all, indistinguishable from success.
    mocker.patch("apkfile.__main__.install_apks", return_value=())
    with pytest.raises(SystemExit) as excinfo:
        main(["install", politedroid_path])
    assert excinfo.value.code == 1
    assert "Nothing was installed" in capsys.readouterr().err


def test_cli_uninstall_prints_confirmation_on_success(capsys, mocker) -> None:
    mocker.patch("apkfile.__main__.uninstall_apks", return_value=("emulator-5554",))
    main(["uninstall", "com.politedroid"])
    out = capsys.readouterr().out
    assert "emulator-5554" in out
    assert "Uninstalled" in out


def test_cli_uninstall_nothing_uninstalled_exits_nonzero(capsys, mocker) -> None:
    mocker.patch("apkfile.__main__.uninstall_apks", return_value=())
    with pytest.raises(SystemExit) as excinfo:
        main(["uninstall", "com.politedroid"])
    assert excinfo.value.code == 1
    assert "Nothing was uninstalled" in capsys.readouterr().err


def test_cli_install_adb_error_prints_clean_message_not_traceback(
    capsys, mocker, politedroid_path: str
) -> None:
    from apkfile.exceptions import AdbError

    mocker.patch(
        "apkfile.__main__.install_apks", side_effect=AdbError("boom on emulator-5554")
    )
    with pytest.raises(SystemExit) as excinfo:
        main(["install", politedroid_path])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "boom on emulator-5554" in err
    assert "Traceback" not in err
