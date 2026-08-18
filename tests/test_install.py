from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from apkfile import install_apks, uninstall_apks
from apkfile.abi import Abi
from apkfile.enums import SplitType
from apkfile.exceptions import AdbError, AdbNotFoundError, InvalidApkError
from apkfile.install import _device_lang_codes, _find_adb


def _has(*parts: str):
    def predicate(args: tuple[str, ...]) -> bool:
        return all(part in args for part in parts)

    return predicate


def _contains(substr: str, args: tuple[str, ...]) -> bool:
    return any(substr in part for part in args)


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

    installed = install_apks(politedroid_path, check=True)

    assert any(_has("push")(c) for c in fake_adb.calls)
    assert any(_has("install-commit", "42")(c) for c in fake_adb.calls)
    assert installed == ("emulator-5554",)


def test_install_with_check_skips_incompatible_sdk(
    fake_adb, politedroid_path: str
) -> None:
    # politedroid.apk has min_sdk_version == 3, so a device with a lower sdk is incompatible.
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "1\n")

    installed = install_apks(politedroid_path, check=True)

    assert not any(_has("push")(c) for c in fake_adb.calls)
    # Nothing was actually installed, even though no AdbError was raised — the device was
    # reached, just had nothing compatible to act on.
    assert installed == ()


def test_install_with_check_skips_apk_whose_only_abi_is_absent_from_device_abilist(
    fake_adb, mocker, tmp_path
) -> None:
    # Regression test for a real device found with `ro.product.cpu.abilist` reporting only
    # "arm64-v8a" (no armeabi-v7a fallback entry, e.g. some arm64-only system images) trying to
    # install an armeabi-v7a-only apk. `Abi.is_compatible_with()`'s generic "a 64-bit ABI can run
    # its 32-bit predecessor" rule used to let this through, and the device's `pm install-commit`
    # then rejected it with INSTALL_FAILED_NO_MATCHING_ABIS — `abilist` is Android's own
    # authoritative, self-reported list, and apkfile must not second-guess it.
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake")
    fake_apk = SimpleNamespace(
        split_type=None,
        split_name=None,
        langs=(),
        abis=(Abi.ARM7,),
        min_sdk_version=None,
        size=1,
        path=apk_path,
    )
    mocker.patch("apkfile.install.ApkFile", side_effect=lambda p: fake_apk)

    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")

    install_apks(str(apk_path), check=True)

    assert not any(_has("push")(c) for c in fake_adb.calls)


def test_install_with_check_installs_apk_whose_abi_is_in_device_abilist(
    fake_adb, mocker, tmp_path
) -> None:
    apk_path = tmp_path / "app.apk"
    apk_path.write_bytes(b"fake")
    fake_apk = SimpleNamespace(
        split_type=None,
        split_name=None,
        langs=(),
        abis=(Abi.ARM7,),
        min_sdk_version=None,
        size=1,
        path=apk_path,
    )
    mocker.patch("apkfile.install.ApkFile", side_effect=lambda p: fake_apk)

    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a,armeabi-v7a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    install_apks(str(apk_path), check=True)

    assert any(_has("push")(c) for c in fake_adb.calls)


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


def test_incompatible_device_still_cleans_up_tmp_dir(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "1\n")  # incompatible sdk

    install_apks(politedroid_path, check=True)

    assert any(_has("rm", "-rf", "/data/local/tmp/xyz")(c) for c in fake_adb.calls)


def test_device_lang_codes_uses_full_plural_locale_list(fake_adb) -> None:
    fake_adb.on(_has("persist.sys.locales"), "en-US,fr-FR,he-IL\n")
    adb = _find_adb(None)
    assert _device_lang_codes((adb, "-s", "emulator-5554")) == {"en", "fr", "he"}


def test_device_lang_codes_falls_back_to_singular_locale_on_old_devices(
    fake_adb,
) -> None:
    fake_adb.on(_has("persist.sys.locales"), "\n")  # empty: pre-Android-7.0 device
    fake_adb.on(_has("persist.sys.locale"), "en-US\n")
    adb = _find_adb(None)
    assert _device_lang_codes((adb, "-s", "emulator-5554")) == {"en"}


def test_device_lang_codes_falls_back_to_settings_provider(fake_adb) -> None:
    # persist.sys.locale(s) both unset (as on a fresh, headless emulator that never went through
    # Setup Wizard) but the live Settings.System value is populated.
    fake_adb.on(_has("persist.sys.locales"), "\n")
    fake_adb.on(_has("persist.sys.locale"), "\n")
    fake_adb.on(_has("system_locales"), "he-IL,en-US\n")
    adb = _find_adb(None)
    assert _device_lang_codes((adb, "-s", "emulator-5554")) == {"he", "en"}


def test_device_lang_codes_final_fallback_to_build_time_default(fake_adb) -> None:
    # Regression coverage for the real bug found against a live emulator: a fresh/headless AVD
    # that never went through Setup Wizard leaves persist.sys.locale(s) AND the settings-provider
    # value completely empty (the latter as the literal string "null", not "") — ro.product.locale
    # (read-only, always present) is the necessary last resort.
    fake_adb.on(_has("persist.sys.locales"), "\n")
    fake_adb.on(_has("persist.sys.locale"), "\n")
    fake_adb.on(_has("system_locales"), "null\n")
    fake_adb.on(_has("ro.product.locale"), "en-US\n")
    adb = _find_adb(None)
    assert _device_lang_codes((adb, "-s", "emulator-5554")) == {"en"}


def test_lang_split_matches_secondary_device_locale_not_just_primary(
    fake_adb, mocker, tmp_path
) -> None:
    # Regression coverage for the persist.sys.locales fix: a device with English as its primary
    # locale but Hebrew also configured should get *both* matching language splits, not just the
    # one matching persist.sys.locale's single reported value.
    base_path = tmp_path / "base.apk"
    en_path = tmp_path / "config.en.apk"
    he_path = tmp_path / "config.he.apk"
    for p in (base_path, en_path, he_path):
        p.write_bytes(b"fake")

    fakes = {
        str(base_path): SimpleNamespace(
            split_type=None,
            langs=(),
            abis=(),
            min_sdk_version=None,
            size=1,
            path=base_path,
        ),
        str(en_path): SimpleNamespace(
            split_type=SplitType.LANGUAGE,
            langs=("en",),
            abis=(),
            min_sdk_version=None,
            size=2,
            path=en_path,
        ),
        str(he_path): SimpleNamespace(
            split_type=SplitType.LANGUAGE,
            langs=("he",),
            abis=(),
            min_sdk_version=None,
            size=3,
            path=he_path,
        ),
    }
    mocker.patch("apkfile.install.ApkFile", side_effect=lambda p: fakes[str(p)])

    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")
    fake_adb.on(_has("persist.sys.locales"), "en-US,he-IL\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    install_apks([str(base_path), str(en_path), str(he_path)], check=True)

    pushed = next(c for c in fake_adb.calls if _has("push")(c))
    assert str(en_path) in pushed
    assert str(he_path) in pushed


def _make_dpi_split_fakes(tmp_path) -> tuple[dict, Path, Path, Path]:
    base_path = tmp_path / "base.apk"
    xhdpi_path = tmp_path / "config.xhdpi.apk"
    xxhdpi_path = tmp_path / "config.xxhdpi.apk"
    for p in (base_path, xhdpi_path, xxhdpi_path):
        p.write_bytes(b"fake")

    fakes = {
        str(base_path): SimpleNamespace(
            split_type=None,
            split_name=None,
            langs=(),
            abis=(),
            min_sdk_version=None,
            size=1,
            path=base_path,
        ),
        str(xhdpi_path): SimpleNamespace(
            split_type=SplitType.DPI,
            split_name="config.xhdpi",
            langs=(),
            abis=(),
            min_sdk_version=None,
            size=2,
            path=xhdpi_path,
        ),
        str(xxhdpi_path): SimpleNamespace(
            split_type=SplitType.DPI,
            split_name="config.xxhdpi",
            langs=(),
            abis=(),
            min_sdk_version=None,
            size=3,
            path=xxhdpi_path,
        ),
    }
    return fakes, base_path, xhdpi_path, xxhdpi_path


def test_dpi_split_falls_back_to_wm_density_when_lcd_density_prop_is_empty(
    fake_adb, mocker, tmp_path
) -> None:
    # Regression test: a real device was found where `getprop ro.sf.lcd_density` returns an empty
    # string (not unset — a real, observed case), which used to crash the whole install with a
    # bare `ValueError` instead of falling back to `wm density`, the modern equivalent.
    fakes, base_path, xhdpi_path, xxhdpi_path = _make_dpi_split_fakes(tmp_path)
    mocker.patch("apkfile.install.ApkFile", side_effect=lambda p: fakes[str(p)])

    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")
    fake_adb.on(_has("getprop", "ro.sf.lcd_density"), "\n")
    fake_adb.on(_has("wm", "density"), "Physical density: 480\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    install_apks([str(base_path), str(xhdpi_path), str(xxhdpi_path)], check=True)

    pushed = next(c for c in fake_adb.calls if _has("push")(c))
    assert (
        str(xxhdpi_path) in pushed
    )  # 480dpi is closer to xxhdpi (480) than xhdpi (320)
    assert str(xhdpi_path) not in pushed


def test_dpi_split_installs_every_split_when_density_is_undeterminable(
    fake_adb, mocker, tmp_path
) -> None:
    # If both `ro.sf.lcd_density` and `wm density` fail to yield a usable number, every dpi split
    # is installed rather than guessing wrong or dropping density-specific resources entirely —
    # same fallback philosophy as the "install every lang split" case.
    fakes, base_path, xhdpi_path, xxhdpi_path = _make_dpi_split_fakes(tmp_path)
    mocker.patch("apkfile.install.ApkFile", side_effect=lambda p: fakes[str(p)])

    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("getprop", "ro.product.cpu.abilist"), "arm64-v8a\n")
    fake_adb.on(_has("getprop", "ro.build.version.sdk"), "33\n")
    fake_adb.on(_has("getprop", "ro.sf.lcd_density"), "\n")
    fake_adb.on(_has("wm", "density"), "\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    install_apks([str(base_path), str(xhdpi_path), str(xxhdpi_path)], check=True)

    pushed = next(c for c in fake_adb.calls if _has("push")(c))
    assert str(xhdpi_path) in pushed
    assert str(xxhdpi_path) in pushed


def test_obb_paths_pushed_after_successful_install(
    fake_adb, politedroid_path: str, tmp_path
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")
    obb = tmp_path / "main.1.com.politedroid.obb"
    obb.write_bytes(b"obb-data")

    install_apks(politedroid_path, check=False, obb_paths=str(obb))

    assert any(
        _has("mkdir", "-p", "/sdcard/Android/obb/com.politedroid")(c)
        for c in fake_adb.calls
    )
    assert any(
        _has("push")(c)
        and "/sdcard/Android/obb/com.politedroid/main.1.com.politedroid.obb" in c
        for c in fake_adb.calls
    )


def test_obb_paths_accepts_multiple_paths(
    fake_adb, politedroid_path: str, tmp_path
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")
    main_obb = tmp_path / "main.1.com.politedroid.obb"
    patch_obb = tmp_path / "patch.1.com.politedroid.obb"
    main_obb.write_bytes(b"main")
    patch_obb.write_bytes(b"patch")

    install_apks(
        politedroid_path, check=False, obb_paths=[str(main_obb), str(patch_obb)]
    )

    assert any(_contains("main.1.com.politedroid.obb", c) for c in fake_adb.calls)
    assert any(_contains("patch.1.com.politedroid.obb", c) for c in fake_adb.calls)


def test_multi_device_one_failure_does_not_prevent_other_device(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(
        _has("devices"),
        "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n",
    )
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(
        _has("push", "emulator-5554"),
        subprocess.CalledProcessError(1, ["adb", "push"], output="", stderr="boom"),
    )
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    with pytest.raises(AdbError, match="emulator-5554"):
        install_apks(politedroid_path, check=False)

    # the second device still got installed despite the first device's push failing.
    assert any(_has("push", "emulator-5556")(c) for c in fake_adb.calls)
    assert any(_has("install-commit", "emulator-5556")(c) for c in fake_adb.calls)


def test_multi_device_mktemp_failure_does_not_abort_other_device(
    fake_adb, politedroid_path: str
) -> None:
    # Regression test: mktemp runs before the per-device apks are even resolved, so a naive
    # try/except placed only around the push/install-* calls would let a mktemp failure on one
    # device abort the whole loop before the next device is ever attempted.
    fake_adb.on(
        _has("devices"),
        "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n",
    )
    fake_adb.on(
        _has("mktemp", "emulator-5554"),
        subprocess.CalledProcessError(
            1, ["adb", "shell", "mktemp"], output="", stderr="permission denied"
        ),
    )
    fake_adb.on(_has("mktemp", "emulator-5556"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    with pytest.raises(AdbError, match="emulator-5554"):
        install_apks(politedroid_path, check=False)

    assert any(_has("push", "emulator-5556")(c) for c in fake_adb.calls)
    assert any(_has("install-commit", "emulator-5556")(c) for c in fake_adb.calls)
    # the failing device never had a tmp_dir, so no rm -rf was attempted for it.
    assert not any(_has("rm", "-rf", "emulator-5554")(c) for c in fake_adb.calls)


def test_install_multi_device_returns_only_devices_that_actually_installed(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(
        _has("devices"),
        "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n",
    )
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(
        _has("getprop", "ro.product.cpu.abilist", "emulator-5554"), "arm64-v8a\n"
    )
    fake_adb.on(_has("getprop", "ro.build.version.sdk", "emulator-5554"), "1\n")
    fake_adb.on(
        _has("getprop", "ro.product.cpu.abilist", "emulator-5556"), "arm64-v8a\n"
    )
    fake_adb.on(_has("getprop", "ro.build.version.sdk", "emulator-5556"), "33\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    installed = install_apks(politedroid_path, check=True)

    # emulator-5554's sdk (1) is below politedroid's min_sdk_version, so only 5556 installs.
    assert installed == ("emulator-5556",)


def test_multi_device_aggregated_error_names_every_failed_device(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(
        _has("devices"),
        "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n",
    )
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(
        _has("push"),
        subprocess.CalledProcessError(1, ["adb", "push"], output="", stderr="boom"),
    )

    with pytest.raises(AdbError) as excinfo:
        install_apks(politedroid_path, check=False)

    message = str(excinfo.value)
    assert "emulator-5554" in message
    assert "emulator-5556" in message


def test_install_flags_passed_to_pm_install_create(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    install_apks(
        politedroid_path,
        check=False,
        grant_permissions=True,
        allow_downgrade=True,
        allow_test_packages=True,
        user="all",
    )

    create_call = next(c for c in fake_adb.calls if _has("install-create")(c))
    assert "-g" in create_call
    assert "-d" in create_call
    assert "-t" in create_call
    assert _has("--user", "all")(create_call)


def test_install_flags_omitted_by_default(fake_adb, politedroid_path: str) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(_has("mktemp"), "/data/local/tmp/xyz\n")
    fake_adb.on(_has("install-create"), "Success: created install session [1]\n")

    install_apks(politedroid_path, check=False)

    create_call = next(c for c in fake_adb.calls if _has("install-create")(c))
    assert "-g" not in create_call
    assert "-d" not in create_call
    assert "-t" not in create_call
    assert "--user" not in create_call


def test_install_with_no_devices_connected_returns_empty(
    fake_adb, politedroid_path: str
) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\n")

    assert install_apks(politedroid_path, check=False) == ()


def test_uninstall_single_device(fake_adb) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")

    uninstalled = uninstall_apks("com.politedroid")

    uninstall_call = next(c for c in fake_adb.calls if _has("uninstall")(c))
    assert "com.politedroid" in uninstall_call
    assert "-k" not in uninstall_call
    assert uninstalled == ("emulator-5554",)


def test_uninstall_flags_passed_through(fake_adb) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")

    uninstall_apks("com.politedroid", keep_data=True, user="10", version_code=4)

    uninstall_call = next(c for c in fake_adb.calls if _has("uninstall")(c))
    assert "-k" in uninstall_call
    assert _has("--user", "10")(uninstall_call)
    assert _has("--versionCode", "4")(uninstall_call)


def test_uninstall_explicit_device_id_skips_devices_listing(fake_adb) -> None:
    uninstall_apks("com.politedroid", device_id="my-device")

    assert not any(c[1:] == ("devices",) for c in fake_adb.calls)
    assert any("my-device" in c for c in fake_adb.calls)


def test_uninstall_adb_not_found_raises(mocker) -> None:
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(AdbNotFoundError):
        uninstall_apks("com.politedroid")


def test_uninstall_failure_raises_adb_error_with_device_context(fake_adb) -> None:
    fake_adb.on(_has("devices"), "List of devices attached\nemulator-5554\tdevice\n")
    fake_adb.on(
        _has("uninstall"),
        subprocess.CalledProcessError(
            1, ["adb", "shell", "pm", "uninstall"], output="", stderr="not installed"
        ),
    )

    with pytest.raises(AdbError, match="emulator-5554"):
        uninstall_apks("com.politedroid")


def test_uninstall_multi_device_one_failure_does_not_prevent_other_device(
    fake_adb,
) -> None:
    fake_adb.on(
        _has("devices"),
        "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n",
    )
    fake_adb.on(
        _has("uninstall", "emulator-5554"),
        subprocess.CalledProcessError(1, ["adb"], output="", stderr="boom"),
    )

    with pytest.raises(AdbError, match="emulator-5554"):
        uninstall_apks("com.politedroid")

    assert any(_has("uninstall", "emulator-5556")(c) for c in fake_adb.calls)
