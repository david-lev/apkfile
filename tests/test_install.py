from __future__ import annotations

import subprocess

import pytest

from apkfile import install_apks
from apkfile.exceptions import AdbError, AdbNotFoundError, InvalidApkError


def _has(*parts: str):
    def predicate(args: tuple[str, ...]) -> bool:
        return all(part in args for part in parts)

    return predicate


def test_adb_not_found_raises(mocker, politedroid_path: str) -> None:
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(AdbNotFoundError):
        install_apks(politedroid_path)


def test_install_without_check_skips_apk_parsing(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("install-create"), "Success: created install session [123]\n")

    install_apks(politedroid_path, check=False)

    assert any(_has("push")(c) for c in fake_adb.calls)
    assert any(_has("install-commit", "123")(c) for c in fake_adb.calls)
    assert any(_has("rm", "-rf")(c) for c in fake_adb.calls)
    # check=False never needs to know the device's abilist/sdk.
    assert not any(_has("getprop", "ro.product.cpu.abilist")(c) for c in fake_adb.calls)


def test_install_with_check_queries_device_and_installs_when_compatible(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a,armeabi-v7a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")
    fake_adb.on(_has("install-create"), "Success: created install session [42]\n")

    install_apks(politedroid_path, check=True)

    assert any(_has("push")(c) for c in fake_adb.calls)
    assert any(_has("install-commit", "42")(c) for c in fake_adb.calls)


def test_install_with_check_skips_incompatible_sdk(
    fake_adb, politedroid_path: str
) -> None:
    # politedroid.apk has min_sdk_version == 3, so a device with a lower sdk is incompatible.
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "1\n")

    install_apks(politedroid_path, check=True)

    assert not any(_has("push")(c) for c in fake_adb.calls)


def test_explicit_device_id_skips_devices_listing(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")
    fake_adb.on(_has("install-create"), "Success: created install session [7]\n")

    install_apks(politedroid_path, device_id="my-device")

    assert not any(c[1:] == ("devices",) for c in fake_adb.calls)
    assert any("my-device" in c for c in fake_adb.calls)


def test_push_failure_raises_adb_error_with_device_context(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(
        _has("push"),
        subprocess.CalledProcessError(
            1, ["adb", "push"], output="", stderr="error: no devices/emulators found"
        ),
    )

    with pytest.raises(AdbError, match="emulator-5554"):
        install_apks(politedroid_path, check=False)

    # cleanup still runs even though the install failed.
    assert any(_has("rm", "-rf")(c) for c in fake_adb.calls)


def test_broken_apk_raises_by_default(fake_adb, tmp_path) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    broken = tmp_path / "broken.apk"
    broken.write_bytes(b"not an apk")

    with pytest.raises(InvalidApkError):
        install_apks(str(broken), check=True)


def test_broken_apk_skipped_when_requested(fake_adb, tmp_path) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    broken = tmp_path / "broken.apk"
    broken.write_bytes(b"not an apk")

    install_apks(str(broken), check=True, skip_broken=True)

    assert not any(_has("push")(c) for c in fake_adb.calls)
