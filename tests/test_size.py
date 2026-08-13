from __future__ import annotations

from apkfile import ApkFile


def test_size_breakdown_categories_sum_to_total(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    sb = apk.size_breakdown
    assert sb.dex > 0
    assert sb.resources > 0
    assert sb.manifest > 0
    assert sb.native_libs == 0
    assert sb.assets == 0
    assert (
        sb.dex
        + sb.resources
        + sb.native_libs
        + sb.assets
        + sb.manifest
        + sb.signing
        + sb.other
        == sb.total_uncompressed
    )
    assert sb.total_compressed <= sb.total_uncompressed


def test_size_breakdown_categorizes_native_libs(apk_with_native_libs: str) -> None:
    apk = ApkFile(apk_with_native_libs)
    assert apk.size_breakdown.native_libs > 0


def test_dex_info_matches_known_counts(
    politedroid_path: str, test_debug_path: str
) -> None:
    politedroid = ApkFile(politedroid_path)
    assert politedroid.dex_info.dex_count == 1
    assert politedroid.dex_info.is_multidex is False
    assert politedroid.dex_info.method_count == 144
    assert politedroid.dex_info.class_count == 10

    test_debug = ApkFile(test_debug_path)
    assert test_debug.dex_info.method_count == 23
    assert test_debug.dex_info.class_count == 7


def test_size_breakdown_and_dex_info_are_summable(
    politedroid_path: str, test_debug_path: str
) -> None:
    a = ApkFile(politedroid_path).size_breakdown
    b = ApkFile(test_debug_path).size_breakdown
    total = a + b
    assert total.total_uncompressed == a.total_uncompressed + b.total_uncompressed

    dex_a = ApkFile(politedroid_path).dex_info
    dex_b = ApkFile(test_debug_path).dex_info
    dex_total = dex_a + dex_b
    assert dex_total.dex_count == 2
    assert dex_total.is_multidex is True
    assert dex_total.method_count == dex_a.method_count + dex_b.method_count
