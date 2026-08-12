from __future__ import annotations

import hashlib
import io
import os
import zipfile

import pytest

from apkfile import Abi, ApkFile, InstallLocation
from apkfile.exceptions import ApkFileError, InvalidApkError


def test_politedroid_basic_fields(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    assert apk.path == politedroid_path
    assert apk.package_name == "com.politedroid"
    assert apk.version_code == 4
    assert apk.version_name == "1.3"
    assert apk.min_sdk_version == 3
    assert apk.install_location == InstallLocation.AUTO
    assert set(apk.permissions) == {
        "android.permission.READ_CALENDAR",
        "android.permission.RECEIVE_BOOT_COMPLETED",
    }
    assert apk.launchable_activity == "com.politedroid.Preferences"
    assert apk.labels == {"": "Polite Droid"}
    assert apk.langs == ()
    assert apk.is_split is False
    assert apk.split_name is None
    assert apk.split_type is None


def test_politedroid_icons_and_densities(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    assert apk.densities == (120, 160, 240, 320)
    assert set(apk.icons) == {120, 160, 240, 320}
    assert all(path.endswith("icon.png") for path in apk.icons.values())


def test_minimal_apk_has_no_permissions_or_native_code(test_debug_path: str) -> None:
    apk = ApkFile(test_debug_path)
    assert apk.package_name == "org.t0t0.androguard.test"
    assert apk.permissions == ()
    assert apk.abis == ()
    assert apk.densities == ()
    assert apk.icons == {}


def test_native_abis_detected_from_lib_folders(apk_with_native_libs: str) -> None:
    apk = ApkFile(apk_with_native_libs)
    assert apk.abis == (Abi.ARM64, Abi.ARM7)


def test_garbage_bytes_raise_invalid_apk_error() -> None:
    with pytest.raises(InvalidApkError):
        ApkFile._from_bytes(b"not an apk" * 5, name="bad.apk")


def test_zip_without_manifest_raises_invalid_apk_error() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(InvalidApkError):
        ApkFile._from_bytes(buf.getvalue(), name="empty.apk")


def test_missing_path_raises_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError):
        ApkFile("does/not/exist.apk")


def test_size_md5_sha256(politedroid_path: str, politedroid_bytes: bytes) -> None:
    apk = ApkFile(politedroid_path)
    assert apk.size == len(politedroid_bytes)
    assert apk.md5 == hashlib.md5(politedroid_bytes).hexdigest()
    assert apk.sha256 == hashlib.sha256(politedroid_bytes).hexdigest()


def test_in_memory_apk_has_no_path_until_saved(
    politedroid_bytes: bytes, tmp_path
) -> None:
    apk = ApkFile._from_bytes(politedroid_bytes, name="politedroid.apk")
    assert apk.path is None
    assert apk.size == len(politedroid_bytes)
    assert apk.md5 == hashlib.md5(politedroid_bytes).hexdigest()

    target = tmp_path / "saved.apk"
    apk.save(target)
    assert apk.path == str(target)
    assert target.read_bytes() == politedroid_bytes


def test_rename_without_path_raises(politedroid_bytes: bytes) -> None:
    apk = ApkFile._from_bytes(politedroid_bytes, name="politedroid.apk")
    with pytest.raises(ApkFileError):
        apk.rename("{package_name}.apk")


def test_rename_formats_from_attributes(tmp_path, politedroid_bytes: bytes) -> None:
    src = tmp_path / "original.apk"
    src.write_bytes(politedroid_bytes)
    apk = ApkFile(src)
    apk.rename("{package_name}-{version_code}.apk")
    assert apk.path == str(tmp_path / "com.politedroid-4.apk")
    assert (tmp_path / "com.politedroid-4.apk").exists()


def test_rename_rejects_non_str_int_attribute(
    tmp_path, politedroid_bytes: bytes
) -> None:
    src = tmp_path / "original.apk"
    src.write_bytes(politedroid_bytes)
    apk = ApkFile(src)
    with pytest.raises(TypeError):
        apk.rename("{labels}.apk")


def test_extract_pulls_manifest(tmp_path, politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    out_dir = tmp_path / "out"
    apk.extract(out_dir, members=["AndroidManifest.xml"])
    assert (out_dir / "AndroidManifest.xml").exists()


def test_as_dict_has_all_documented_fields(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    as_dict = apk.as_dict()
    assert as_dict["package_name"] == "com.politedroid"
    assert set(as_dict) == set(ApkFile._FIELDS)


def test_repr(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    assert repr(apk) == "ApkFile(pkg='com.politedroid', version=4)"


def test_install_with_path_delegates_to_install_apks(
    politedroid_path: str, mocker
) -> None:
    mock_install = mocker.patch("apkfile.install.install_apks")
    apk = ApkFile(politedroid_path)
    apk.install(upgrade=True)
    mock_install.assert_called_once_with(
        apks=politedroid_path,
        check=True,
        upgrade=True,
        device_id=None,
        skip_broken=False,
        installer=None,
        originating_uri=None,
        adb_path=None,
    )


def test_install_without_path_writes_to_temp_file_first(
    politedroid_bytes: bytes, mocker
) -> None:
    mock_install = mocker.patch("apkfile.install.install_apks")
    apk = ApkFile._from_bytes(politedroid_bytes, name="politedroid.apk")
    apk.install()
    assert mock_install.call_count == 1
    tmp_path = mock_install.call_args.kwargs["apks"]
    assert tmp_path.endswith("politedroid.apk")
    # the temp dir is cleaned up once install() returns.
    assert not os.path.exists(tmp_path)
    # the object itself is untouched by the temporary write.
    assert apk.path is None
