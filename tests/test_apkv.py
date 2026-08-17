from __future__ import annotations

import json
import zipfile
from collections.abc import Callable

import pytest

from apkfile import ApkFile, ApkvFile
from apkfile.exceptions import EncryptedBundleError, InvalidBundleError


def test_apkv_plain_basic_fields(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv())
    assert apkv.package_name == "com.politedroid"
    assert apkv.version_code == 4
    assert apkv.version_name == "1.3"
    assert apkv.app_name == "Polite Droid"
    assert apkv.apkv_version == 2
    assert apkv.min_sdk_version == 3
    assert apkv.target_sdk_version == 29
    assert apkv.encrypted is False
    assert apkv.exported_at is not None
    assert apkv.exported_at.year == 2025


def test_apkv_base_and_splits(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv())
    assert isinstance(apkv.base, ApkFile)
    assert apkv.base.package_name == "com.politedroid"
    assert len(apkv.splits) == 1
    assert apkv.splits[0].package_name == "org.t0t0.androguard.test"


def test_apkv_without_split(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv(with_split=False))
    assert apkv.splits == ()
    assert apkv.base.package_name == "com.politedroid"


def test_apkv_encrypted_requires_password(make_apkv: Callable[..., str]) -> None:
    path = make_apkv(encrypted=True, password="hunter2")
    with pytest.raises(EncryptedBundleError):
        ApkvFile(path)


def test_apkv_encrypted_wrong_password_raises(make_apkv: Callable[..., str]) -> None:
    path = make_apkv(encrypted=True, password="hunter2")
    with pytest.raises(EncryptedBundleError):
        ApkvFile(path, password="wrong-password")


def test_apkv_encrypted_correct_password(make_apkv: Callable[..., str]) -> None:
    path = make_apkv(encrypted=True, password="hunter2")
    apkv = ApkvFile(path, password="hunter2")
    assert apkv.package_name == "com.politedroid"
    assert apkv.encrypted is True
    assert apkv.base.package_name == "com.politedroid"
    assert len(apkv.splits) == 1


def test_apkv_plain_ignores_password(make_apkv: Callable[..., str]) -> None:
    # a plain archive doesn't need one; a (wrong or right) password shouldn't matter.
    apkv = ApkvFile(make_apkv(), password="irrelevant")
    assert apkv.encrypted is False
    assert apkv.package_name == "com.politedroid"


def test_apkv_base_name_prefers_base_apk(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv())
    assert apkv.base.package_name == "com.politedroid"  # from base.apk, not the split


def test_apkv_base_name_single_split_is_base(
    tmp_path, politedroid_bytes: bytes
) -> None:
    manifest = {
        "format": "apkv",
        "formatVersion": 2,
        "packageName": "com.politedroid",
        "versionName": "1.3",
        "versionCode": 4,
        "label": "Polite Droid",
        "isSplit": False,
        "splits": ["original_name.apk"],
        "encrypted": False,
        "hasIcon": False,
    }
    path = tmp_path / "single.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("original_name.apk", politedroid_bytes)
    apkv = ApkvFile(path)
    assert apkv.base.package_name == "com.politedroid"
    assert apkv.splits == ()


def test_apkv_base_name_falls_back_to_non_prefixed_entry(
    tmp_path, politedroid_bytes: bytes, test_debug_bytes: bytes
) -> None:
    # no "base.apk" and more than one entry: the one without a split-prefix wins.
    manifest = {
        "format": "apkv",
        "formatVersion": 2,
        "packageName": "com.politedroid",
        "versionName": "1.3",
        "versionCode": 4,
        "label": "Polite Droid",
        "isSplit": True,
        "splits": ["split_config.arm64_v8a.apk", "com.politedroid.apk"],
        "encrypted": False,
        "hasIcon": False,
    }
    path = tmp_path / "heuristic.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("com.politedroid.apk", politedroid_bytes)
        z.writestr("split_config.arm64_v8a.apk", test_debug_bytes)
    apkv = ApkvFile(path)
    assert apkv.base.package_name == "com.politedroid"
    assert len(apkv.splits) == 1
    assert apkv.splits[0].package_name == "org.t0t0.androguard.test"


def test_apkv_checksum_verification_passes(
    make_apkv: Callable[..., str], politedroid_bytes: bytes, test_debug_bytes: bytes
) -> None:
    import hashlib

    path = make_apkv(
        extra_manifest={
            "checksums": {
                "base.apk": f"sha256:{hashlib.sha256(politedroid_bytes).hexdigest()}",
                "split_config.arm64_v8a.apk": f"sha256:{hashlib.sha256(test_debug_bytes).hexdigest()}",
            }
        }
    )
    apkv = ApkvFile(path, verify_checksums=True)
    assert apkv.package_name == "com.politedroid"


def test_apkv_checksum_verification_fails_on_mismatch(
    tmp_path, politedroid_bytes: bytes
) -> None:
    manifest = {
        "format": "apkv",
        "formatVersion": 2,
        "packageName": "com.politedroid",
        "versionName": "1.3",
        "versionCode": 4,
        "label": "Polite Droid",
        "isSplit": False,
        "splits": ["base.apk"],
        "encrypted": False,
        "hasIcon": False,
        "checksums": {"base.apk": "sha256:" + "0" * 64},
    }
    path = tmp_path / "bad-checksum.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("base.apk", politedroid_bytes)
    with pytest.raises(InvalidBundleError, match="base.apk"):
        ApkvFile(path, verify_checksums=True)
    # verification is opt-in: skipped entirely by default.
    assert ApkvFile(path).package_name == "com.politedroid"


def test_apkv_not_apkv_format_raises(tmp_path, politedroid_bytes: bytes) -> None:
    manifest = {"format": "something-else", "splits": ["base.apk"]}
    path = tmp_path / "not-apkv.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("base.apk", politedroid_bytes)
    with pytest.raises(InvalidBundleError):
        ApkvFile(path)


def test_apkv_no_splits_declared_raises(tmp_path) -> None:
    manifest = {
        "format": "apkv",
        "formatVersion": 2,
        "packageName": "com.politedroid",
        "versionCode": 4,
        "label": "Polite Droid",
        "splits": [],
    }
    path = tmp_path / "no-splits.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(InvalidBundleError):
        ApkvFile(path)


def test_apkv_missing_required_key_raises(tmp_path) -> None:
    manifest = {"format": "apkv", "formatVersion": 2, "splits": ["base.apk"]}
    path = tmp_path / "missing-key.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(InvalidBundleError):
        ApkvFile(path)


def test_apkv_icon_bytes_plain(tmp_path, politedroid_bytes: bytes) -> None:
    manifest = {
        "format": "apkv",
        "formatVersion": 2,
        "packageName": "com.politedroid",
        "versionCode": 4,
        "label": "Polite Droid",
        "splits": ["base.apk"],
        "hasIcon": True,
    }
    path = tmp_path / "with-icon.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("base.apk", politedroid_bytes)
        z.writestr("icon.webp", b"fake-webp-icon")
    apkv = ApkvFile(path)
    assert apkv.icon_bytes == b"fake-webp-icon"


def test_apkv_icon_bytes_none_when_absent(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv())
    assert apkv.icon_bytes is None


def test_apkv_encrypted_icon_bytes(
    tmp_path, politedroid_bytes: bytes, apkv_encrypt: Callable[[bytes, str], bytes]
) -> None:
    # build directly (make_apkv doesn't attach an icon) to cover the icon.enc decrypt path.
    import io

    password = "hunter2"
    manifest = {
        "format": "apkv",
        "formatVersion": 2,
        "packageName": "com.politedroid",
        "versionCode": 4,
        "label": "Polite Droid",
        "splits": ["base.apk"],
        "encrypted": True,
        "hasIcon": True,
    }
    payload_buf = io.BytesIO()
    with zipfile.ZipFile(payload_buf, "w") as pz:
        pz.writestr("base.apk", politedroid_bytes)

    path = tmp_path / "encrypted-icon.apkv"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(".apkv_enc", b"")
        z.writestr(
            "header.json",
            json.dumps(
                {
                    "packageName": "com.politedroid",
                    "label": "Polite Droid",
                    "encrypted": True,
                    "hasIcon": True,
                }
            ),
        )
        z.writestr(
            "manifest.enc", apkv_encrypt(json.dumps(manifest).encode(), password)
        )
        z.writestr("payload.enc", apkv_encrypt(payload_buf.getvalue(), password))
        z.writestr("icon.enc", apkv_encrypt(b"fake-webp-icon", password))

    apkv = ApkvFile(path, password=password)
    assert apkv.icon_bytes == b"fake-webp-icon"


def test_apkv_as_dict(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv())
    as_dict = apkv.as_dict()
    assert as_dict["app_name"] == "Polite Droid"
    assert as_dict["apkv_version"] == 2


def test_apkv_rename_plain(make_apkv: Callable[..., str]) -> None:
    apkv = ApkvFile(make_apkv())
    original_dir = apkv.path.parent
    apkv.rename("{package_name}-{version_code}.apkv")
    assert apkv.path == original_dir / "com.politedroid-4.apkv"
    assert apkv.base.package_name == "com.politedroid"


def test_apkv_rename_encrypted(make_apkv: Callable[..., str]) -> None:
    path = make_apkv(encrypted=True, password="hunter2")
    apkv = ApkvFile(path, password="hunter2")
    original_dir = apkv.path.parent
    apkv.rename("{package_name}-{version_code}.apkv")
    assert apkv.path == original_dir / "com.politedroid-4.apkv"
    # the decrypted in-memory payload zip is untouched by the on-disk rename.
    assert apkv.base.package_name == "com.politedroid"
    assert apkv.splits[0].package_name == "org.t0t0.androguard.test"


def test_apkv_install_extracts_to_temp_dir_and_calls_install_apks(
    make_apkv: Callable[..., str], mocker
) -> None:
    mock_install = mocker.patch("apkfile.install.install_apks")
    apkv = ApkvFile(make_apkv())
    apkv.install(upgrade=True)
    assert mock_install.call_count == 1
    kwargs = mock_install.call_args.kwargs
    assert kwargs["upgrade"] is True
    assert len(kwargs["apks"]) == 2  # base + 1 split
