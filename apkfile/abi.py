"""Android ABI (application binary interface) support."""

from __future__ import annotations

from enum import Enum

__all__ = ["Abi"]


class Abi(str, Enum):
    """
    Android supported ABIs.

    See the [Android documentation](https://developer.android.com/ndk/guides/abis).

    Attributes:
        ARM: armeabi
        ARM7: armeabi-v7a
        ARM64: arm64-v8a
        X86: x86
        X86_64: x86_64
        UNKNOWN: An ABI apkfile does not recognize.
    """

    ARM = "armeabi"
    ARM7 = "armeabi-v7a"
    ARM64 = "arm64-v8a"
    X86 = "x86"
    X86_64 = "x86_64"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> Abi:
        return cls.UNKNOWN

    def is_compatible_with(self, other: Abi) -> bool:
        """Whether a device with this ABI can run an APK built for `other`."""
        if self == other:
            return True
        return other in _COMPATIBILITY_MAP[self]

    @classmethod
    def all(cls) -> tuple[Abi, ...]:
        """All the supported (i.e. non-`UNKNOWN`) ABIs."""
        return tuple(abi for abi in cls if abi is not cls.UNKNOWN)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


# Each 64-bit ABI is backward compatible with its own 32-bit predecessor (arm64-v8a runs
# armeabi-v7a/armeabi; x86_64 runs x86), but the ARM and x86 instruction-set families are NOT
# cross-compatible on stock Android — there is no general-purpose ARM<->x86 translation layer in
# AOSP (some OEM/emulator images ship one, e.g. libhoudini, but it isn't guaranteed and apkfile
# doesn't assume it). See https://developer.android.com/ndk/guides/abis.
_COMPATIBILITY_MAP: dict[Abi, frozenset[Abi]] = {
    Abi.X86_64: frozenset({Abi.X86}),
    Abi.X86: frozenset(),
    Abi.ARM64: frozenset({Abi.ARM7, Abi.ARM}),
    Abi.ARM7: frozenset({Abi.ARM}),
    Abi.ARM: frozenset(),
    Abi.UNKNOWN: frozenset(),
}
