from __future__ import annotations

import json

from apkfile import Abi


def test_abi_equals_plain_string() -> None:
    assert Abi.ARM64 == "arm64-v8a"
    assert Abi("arm64-v8a") is Abi.ARM64


def test_abi_unknown_value_falls_back() -> None:
    assert Abi("something-weird") is Abi.UNKNOWN


def test_abi_all_excludes_unknown() -> None:
    assert Abi.UNKNOWN not in Abi.all()
    assert set(Abi.all()) == {Abi.ARM, Abi.ARM7, Abi.ARM64, Abi.X86, Abi.X86_64}


def test_abi_json_serializes_as_plain_string() -> None:
    assert json.dumps(Abi.ARM64) == '"arm64-v8a"'


def test_abi_is_compatible_with_self() -> None:
    assert Abi.ARM7.is_compatible_with(Abi.ARM7)


def test_64bit_device_runs_32bit_and_legacy_apks() -> None:
    assert Abi.ARM64.is_compatible_with(Abi.ARM7)
    assert Abi.ARM64.is_compatible_with(Abi.ARM)
    assert Abi.X86_64.is_compatible_with(Abi.X86)
    assert Abi.X86_64.is_compatible_with(Abi.ARM64)


def test_32bit_device_cannot_run_64bit_apks() -> None:
    assert not Abi.ARM7.is_compatible_with(Abi.ARM64)
    assert not Abi.ARM.is_compatible_with(Abi.ARM7)


def test_arm_has_no_compatible_targets() -> None:
    # ARM is the narrowest ABI in the compatibility map: nothing lists it as a target.
    assert not Abi.ARM.is_compatible_with(Abi.X86)
    assert not Abi.ARM.is_compatible_with(Abi.ARM64)


def test_unknown_is_compatible_with_nothing() -> None:
    assert not Abi.UNKNOWN.is_compatible_with(Abi.ARM)
    assert Abi.UNKNOWN.is_compatible_with(Abi.UNKNOWN)
