from __future__ import annotations

from apkfile import ApkFile
from apkfile._resources import DensityBucket, ScreenSize


def test_density_bucket_dpi_values() -> None:
    assert DensityBucket.LDPI.dpi == 120
    assert DensityBucket.MDPI.dpi == 160
    assert DensityBucket.TVDPI.dpi == 213
    assert DensityBucket.HDPI.dpi == 240
    assert DensityBucket.XHDPI.dpi == 320
    assert DensityBucket.XXHDPI.dpi == 480
    assert DensityBucket.XXXHDPI.dpi == 640
    assert DensityBucket.ANY.dpi == 65534
    assert DensityBucket.NONE.dpi == 65535
    assert DensityBucket.DEFAULT.dpi == 0


def test_density_bucket_from_dpi_roundtrips() -> None:
    assert DensityBucket.from_dpi(320) is DensityBucket.XHDPI
    assert DensityBucket.from_dpi(65534) is DensityBucket.ANY
    assert DensityBucket.from_dpi(999) is None


def test_icons_are_sorted_by_density_and_have_named_buckets(
    politedroid_path: str,
) -> None:
    apk = ApkFile(politedroid_path)
    densities = [icon.density for icon in apk.icons]
    assert densities == sorted(densities)
    buckets = {icon.bucket for icon in apk.icons}
    assert buckets == {
        DensityBucket.LDPI,
        DensityBucket.MDPI,
        DensityBucket.HDPI,
        DensityBucket.XHDPI,
    }


def test_icon_read_bytes_and_extract(politedroid_path: str, tmp_path) -> None:
    apk = ApkFile(politedroid_path)
    icon = apk.icons[0]
    data = icon.read_bytes()
    assert data.startswith(b"\x89PNG")

    out = tmp_path / "icon.png"
    icon.extract(out)
    assert out.read_bytes() == data


def test_icon_equality_ignores_owning_apk(politedroid_path: str) -> None:
    apk_a = ApkFile(politedroid_path)
    apk_b = ApkFile(politedroid_path)
    # two Icon instances from two different ApkFile objects, describing the same resource,
    # should compare equal -- the private `_apk` back-reference is excluded from equality.
    assert apk_a.icons[0] == apk_b.icons[0]
    assert apk_a.icons[0] is not apk_b.icons[0]


def test_best_icon_picks_highest_density_at_or_below_max_dpi(
    politedroid_path: str,
) -> None:
    apk = ApkFile(politedroid_path)
    assert apk.best_icon().density == 320
    assert apk.best_icon(max_dpi=200).density == 160
    # politedroid.apk has no density=0 ("default") icon, so nothing qualifies below 120dpi.
    assert apk.best_icon(max_dpi=1) is None


def test_best_icon_returns_none_when_no_icons(test_debug_path: str) -> None:
    apk = ApkFile(test_debug_path)
    assert apk.icons == ()
    assert apk.best_icon() is None


def test_supported_screens_is_enum(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    # politedroid.apk's manifest has no <supports-screens>, so this is empty; assert the type
    # contract holds structurally regardless.
    assert all(isinstance(s, ScreenSize) for s in apk.supported_screens)
