from __future__ import annotations

import json
import zipfile
from collections.abc import Callable

import pytest

from apkfile import ApkFile, ApkmFile, ApksFile, XapkFile
from apkfile.exceptions import ApkFileError, InvalidApkError, InvalidBundleError


def test_apkm_eager_fields_do_not_require_parsing_splits(
    make_apkm: Callable[..., str],
) -> None:
    apkm = ApkmFile(make_apkm())
    assert apkm.package_name == "com.politedroid"
    assert apkm.version_code == 4
    assert apkm.app_name == "Polite Droid"
    assert apkm.apkm_version == 2
    assert apkm.min_sdk_version == 3
    assert apkm.version_name == "1.3"
    # base/splits haven't been touched by any of the above (still lazy).
    assert "base" not in apkm.__dict__
    assert "splits" not in apkm.__dict__


def test_apkm_target_sdk_version_falls_back_to_base(
    make_apkm: Callable[..., str],
) -> None:
    # apkm's info.json never carries target_sdk_version; falls back to the base apk's value
    # (politedroid.apk itself has no target_sdk_version either, so this resolves to None).
    apkm = ApkmFile(make_apkm())
    assert apkm.target_sdk_version is None


def test_apkm_base_and_splits(make_apkm: Callable[..., str]) -> None:
    apkm = ApkmFile(make_apkm())
    assert isinstance(apkm.base, ApkFile)
    assert apkm.base.path is None
    assert apkm.base.package_name == "com.politedroid"
    assert len(apkm.splits) == 1
    assert apkm.splits[0].package_name == "org.t0t0.androguard.test"


def test_apkm_without_splits(make_apkm: Callable[..., str]) -> None:
    apkm = ApkmFile(make_apkm(with_split=False))
    assert apkm.splits == ()
    assert set(apkm.permissions) == set(apkm.base.permissions)


def test_apkm_aggregates_permissions_and_abis_from_base_and_splits(
    make_apkm: Callable[..., str],
) -> None:
    apkm = ApkmFile(make_apkm())
    assert set(apkm.permissions) == set(apkm.base.permissions) | set(
        apkm.splits[0].permissions
    )
    assert set(apkm.langs) == set(apkm.base.langs) | set(apkm.splits[0].langs)


def test_apkm_labels_base_wins_over_splits_on_conflict(
    make_apkm: Callable[..., str],
) -> None:
    apkm = ApkmFile(make_apkm())
    # base has a default-locale label; splits don't, so it should simply be present.
    assert apkm.labels[""] == "Polite Droid"


def test_apkm_signing_and_security_delegate_to_base(
    make_apkm: Callable[..., str],
) -> None:
    apkm = ApkmFile(make_apkm())
    assert apkm.signing == apkm.base.signing
    assert apkm.security == apkm.base.security


def test_apkm_size_breakdown_and_dex_info_aggregate_base_and_splits(
    make_apkm: Callable[..., str],
) -> None:
    apkm = ApkmFile(make_apkm())
    assert (
        apkm.size_breakdown == apkm.base.size_breakdown + apkm.splits[0].size_breakdown
    )
    assert apkm.dex_info == apkm.base.dex_info + apkm.splits[0].dex_info
    assert apkm.dex_info.dex_count == 2


def test_apkm_icon(make_apkm: Callable[..., str]) -> None:
    apkm = ApkmFile(make_apkm())
    assert apkm.icon_bytes == b"fake-icon"


def test_apkm_extract_icon(make_apkm: Callable[..., str], tmp_path) -> None:
    apkm = ApkmFile(make_apkm())
    out = tmp_path / "icon.png"
    apkm.extract_icon(out)
    assert out.read_bytes() == b"fake-icon"


def test_apkm_missing_manifest_raises(tmp_path) -> None:
    path = tmp_path / "broken.apkm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("base.apk", b"not-a-real-apk")
    with pytest.raises(InvalidBundleError):
        ApkmFile(path)


def test_apkm_invalid_json_raises(tmp_path) -> None:
    path = tmp_path / "broken.apkm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("info.json", "{not valid json")
        z.writestr("base.apk", b"not-a-real-apk")
    with pytest.raises(InvalidBundleError):
        ApkmFile(path)


def test_apkm_broken_split_raises_by_default(
    tmp_path, politedroid_bytes: bytes
) -> None:
    info = {
        "app_name": "Polite Droid",
        "apkm_version": 2,
        "pname": "com.politedroid",
        "versioncode": 4,
        "min_api": 3,
    }
    path = tmp_path / "broken-split.apkm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("info.json", json.dumps(info))
        z.writestr("base.apk", politedroid_bytes)
        z.writestr("split_broken.apk", b"not a real apk")
    apkm = ApkmFile(path)
    with pytest.raises(InvalidApkError):  # raised lazily, on first .splits access
        _ = apkm.splits


def test_apkm_broken_split_skipped_when_requested(
    tmp_path, politedroid_bytes: bytes
) -> None:
    info = {
        "app_name": "Polite Droid",
        "apkm_version": 2,
        "pname": "com.politedroid",
        "versioncode": 4,
        "min_api": 3,
    }
    path = tmp_path / "broken-split.apkm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("info.json", json.dumps(info))
        z.writestr("base.apk", politedroid_bytes)
        z.writestr("split_broken.apk", b"not a real apk")
    apkm = ApkmFile(path, skip_broken_splits=True)
    assert apkm.splits == ()


def test_apkm_install_extracts_to_temp_dir_and_calls_install_apks(
    make_apkm: Callable[..., str], mocker
) -> None:
    mock_install = mocker.patch("apkfile.install.install_apks")
    apkm = ApkmFile(make_apkm())
    apkm.install(upgrade=True)
    assert mock_install.call_count == 1
    kwargs = mock_install.call_args.kwargs
    assert kwargs["upgrade"] is True
    apk_paths = kwargs["apks"]
    assert len(apk_paths) == 2  # base + 1 split
    assert all(p.suffix == ".apk" for p in apk_paths)


def test_apkm_as_dict_and_repr(make_apkm: Callable[..., str]) -> None:
    apkm = ApkmFile(make_apkm())
    as_dict = apkm.as_dict()
    assert as_dict["app_name"] == "Polite Droid"
    assert as_dict["apkm_version"] == 2
    assert repr(apkm) == "ApkmFile(pkg='com.politedroid', version=4, splits=1)"


def test_xapk_basic_fields(make_xapk: Callable[..., str]) -> None:
    xapk = XapkFile(make_xapk())
    assert xapk.package_name == "com.politedroid"
    assert xapk.app_name == "Polite Droid"
    assert xapk.xapk_version == 2
    assert xapk.min_sdk_version == 3
    assert len(xapk.splits) == 1


def test_xapk_signing_security_size_dex(make_xapk: Callable[..., str]) -> None:
    xapk = XapkFile(make_xapk())
    assert xapk.signing == xapk.base.signing
    assert xapk.security == xapk.base.security
    assert (
        xapk.size_breakdown == xapk.base.size_breakdown + xapk.splits[0].size_breakdown
    )
    assert xapk.dex_info == xapk.base.dex_info + xapk.splits[0].dex_info
    assert xapk.dex_info.dex_count == 2
    assert "android.permission.READ_CALENDAR" in xapk.security.dangerous_permissions


def test_apks_v2(make_apks: Callable[..., str]) -> None:
    apks = ApksFile(make_apks(meta_version=2))
    assert apks.package_name == "com.politedroid"
    assert apks.app_name == "Polite Droid"
    assert apks.meta_version == 2


def test_apks_v1_fallback(make_apks: Callable[..., str]) -> None:
    apks = ApksFile(make_apks(meta_version=1))
    assert apks.package_name == "com.politedroid"
    assert apks.meta_version == 1


def test_apks_signing_security_size_dex(make_apks: Callable[..., str]) -> None:
    apks = ApksFile(make_apks())
    assert apks.signing == apks.base.signing
    assert apks.signing.is_debug_signed is False
    assert apks.security == apks.base.security
    assert (
        apks.size_breakdown == apks.base.size_breakdown + apks.splits[0].size_breakdown
    )
    assert apks.dex_info == apks.base.dex_info + apks.splits[0].dex_info


def test_missing_base_apk_entry_raises_lazily(
    tmp_path, politedroid_bytes: bytes
) -> None:
    info = {
        "app_name": "Polite Droid",
        "apkm_version": 2,
        "pname": "com.politedroid",
        "versioncode": 4,
        "min_api": 3,
    }
    path = tmp_path / "no-base.apkm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("info.json", json.dumps(info))
        # no base.apk entry at all
    apkm = ApkmFile(path)
    assert apkm.package_name == "com.politedroid"  # eager fields still fine
    with pytest.raises(InvalidBundleError):
        _ = apkm.base


def test_icon_bytes_is_none_when_archive_has_no_icon(
    tmp_path, politedroid_bytes: bytes
) -> None:
    info = {
        "app_name": "Polite Droid",
        "apkm_version": 2,
        "pname": "com.politedroid",
        "versioncode": 4,
        "min_api": 3,
    }
    path = tmp_path / "no-icon.apkm"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("info.json", json.dumps(info))
        z.writestr("base.apk", politedroid_bytes)
        # no icon.png entry
    apkm = ApkmFile(path)
    assert apkm.icon_bytes is None
    with pytest.raises(ApkFileError):
        apkm.extract_icon(tmp_path / "icon.png")


def test_bundle_rename(make_apkm: Callable[..., str]) -> None:
    apkm = ApkmFile(make_apkm())
    original_dir = apkm.path.parent
    apkm.rename("{package_name}-{version_code}.apkm")
    assert apkm.path == original_dir / "com.politedroid-4.apkm"
    # the renamed file is still readable (zip handle was reopened against the new path).
    assert apkm.base.package_name == "com.politedroid"


def test_bundle_extract_and_as_zip_file(
    make_apkm: Callable[..., str], tmp_path
) -> None:
    apkm = ApkmFile(make_apkm())
    with apkm.as_zip_file() as zf:
        assert "info.json" in zf.namelist()
    out_dir = tmp_path / "extracted"
    apkm.extract(out_dir, members=["info.json"])
    assert (out_dir / "info.json").exists()
