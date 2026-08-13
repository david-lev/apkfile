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


def test_cli_install_passes_all_flags_through(mocker, politedroid_path: str) -> None:
    mock_install = mocker.patch("apkfile.__main__.install_apks")
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
        adb_path=None,
    )
