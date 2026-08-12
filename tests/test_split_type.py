from __future__ import annotations

from apkfile import Abi
from apkfile.enums import SplitType, classify_split


def test_classify_dpi_split() -> None:
    assert classify_split("config.xxhdpi", langs=(), abis=()) is SplitType.DPI
    assert classify_split("config.ldpi", langs=(), abis=()) is SplitType.DPI


def test_classify_language_split() -> None:
    assert (
        classify_split("config.en", langs=("en", "fr"), abis=()) is SplitType.LANGUAGE
    )
    assert (
        classify_split("config.pt-BR", langs=("pt-BR",), abis=()) is SplitType.LANGUAGE
    )


def test_classify_abi_split() -> None:
    assert (
        classify_split("config.arm64_v8a", langs=(), abis=(Abi.ARM64,)) is SplitType.ABI
    )


def test_classify_other_split() -> None:
    # not a dpi suffix, not a known lang, and not exactly one abi -> OTHER
    assert (
        classify_split("feature.dynamic_module", langs=(), abis=()) is SplitType.OTHER
    )
    assert (
        classify_split("config.weird", langs=(), abis=(Abi.ARM, Abi.ARM64))
        is SplitType.OTHER
    )


def test_classify_uses_last_dot_segment_only() -> None:
    assert classify_split("com.example.config.hdpi", langs=(), abis=()) is SplitType.DPI
