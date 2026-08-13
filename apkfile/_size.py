"""APK size composition and DEX statistics.

DEX method/class/string counts are read straight off each ``classesN.dex``'s fixed-size header with
``struct`` — no need for androguard's full ``DEX``/bytecode-analysis machinery just to count things.
See the `dex format spec <https://source.android.com/docs/core/runtime/dex-format#header-item>`_.
"""

from __future__ import annotations

import struct
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from androguard.core.apk import APK as _AndroguardAPK

__all__ = ["DexInfo", "SizeBreakdown"]

# Offsets (bytes) of the relevant `uint32` fields in a dex `header_item`.
_STRING_IDS_SIZE_OFFSET = 56
_METHOD_IDS_SIZE_OFFSET = 88
_CLASS_DEFS_SIZE_OFFSET = 96


@dataclass(frozen=True, slots=True)
class SizeBreakdown:
    """
    An APK's on-disk size, broken down by content category.

    All fields except :attr:`total_compressed` are uncompressed (on-device) sizes in bytes.

    Attributes:
        dex: Size of ``*.dex`` files (compiled bytecode).
        resources: Size of ``resources.arsc`` and ``res/``.
        native_libs: Size of ``lib/`` (native ``.so`` libraries).
        assets: Size of ``assets/``.
        manifest: Size of ``AndroidManifest.xml``.
        signing: Size of ``META-INF/`` (signing block + JAR signing files).
        other: Size of everything else.
        total_uncompressed: The sum of every entry's uncompressed size.
        total_compressed: The sum of every entry's compressed (as stored in the zip) size.
    """

    dex: int
    resources: int
    native_libs: int
    assets: int
    manifest: int
    signing: int
    other: int
    total_uncompressed: int
    total_compressed: int

    def __add__(self, other: SizeBreakdown) -> SizeBreakdown:
        if not isinstance(other, SizeBreakdown):
            return NotImplemented
        return SizeBreakdown(
            dex=self.dex + other.dex,
            resources=self.resources + other.resources,
            native_libs=self.native_libs + other.native_libs,
            assets=self.assets + other.assets,
            manifest=self.manifest + other.manifest,
            signing=self.signing + other.signing,
            other=self.other + other.other,
            total_uncompressed=self.total_uncompressed + other.total_uncompressed,
            total_compressed=self.total_compressed + other.total_compressed,
        )


@dataclass(frozen=True, slots=True)
class DexInfo:
    """
    Aggregate statistics across an APK's ``classesN.dex`` files.

    Attributes:
        dex_count: How many ``classesN.dex`` files the APK contains.
        is_multidex: Whether the APK has more than one dex file.
        method_count: Total number of method references across every dex file.
        class_count: Total number of class definitions across every dex file.
        string_count: Total number of string pool entries across every dex file.
    """

    dex_count: int
    is_multidex: bool
    method_count: int
    class_count: int
    string_count: int

    def __add__(self, other: DexInfo) -> DexInfo:
        if not isinstance(other, DexInfo):
            return NotImplemented
        dex_count = self.dex_count + other.dex_count
        return DexInfo(
            dex_count=dex_count,
            is_multidex=dex_count > 1,
            method_count=self.method_count + other.method_count,
            class_count=self.class_count + other.class_count,
            string_count=self.string_count + other.string_count,
        )


def _category(name: str) -> str:
    if name == "AndroidManifest.xml":
        return "manifest"
    if name.endswith(".dex"):
        return "dex"
    if name == "resources.arsc" or name.startswith("res/"):
        return "resources"
    if name.startswith("lib/"):
        return "native_libs"
    if name.startswith("assets/"):
        return "assets"
    if name.startswith("META-INF/"):
        return "signing"
    return "other"


def build_size_breakdown(zip_file: zipfile.ZipFile) -> SizeBreakdown:
    """Build a :class:`SizeBreakdown` from an APK's zip entries."""
    totals = {
        "dex": 0,
        "resources": 0,
        "native_libs": 0,
        "assets": 0,
        "manifest": 0,
        "signing": 0,
        "other": 0,
    }
    total_uncompressed = 0
    total_compressed = 0
    for info in zip_file.infolist():
        totals[_category(info.filename)] += info.file_size
        total_uncompressed += info.file_size
        total_compressed += info.compress_size
    return SizeBreakdown(
        total_uncompressed=total_uncompressed,
        total_compressed=total_compressed,
        **totals,
    )


def _parse_dex_header(data: bytes) -> tuple[int, int, int]:
    (string_count,) = struct.unpack_from("<I", data, _STRING_IDS_SIZE_OFFSET)
    (method_count,) = struct.unpack_from("<I", data, _METHOD_IDS_SIZE_OFFSET)
    (class_count,) = struct.unpack_from("<I", data, _CLASS_DEFS_SIZE_OFFSET)
    return string_count, method_count, class_count


def build_dex_info(apk: _AndroguardAPK) -> DexInfo:
    """Build a :class:`DexInfo` by reading each dex file's header (no bytecode parsing)."""
    dex_count = 0
    method_count = 0
    class_count = 0
    string_count = 0
    for data in apk.get_all_dex():
        dex_count += 1
        strings, methods, classes = _parse_dex_header(data)
        string_count += strings
        method_count += methods
        class_count += classes
    return DexInfo(
        dex_count=dex_count,
        is_multidex=dex_count > 1,
        method_count=method_count,
        class_count=class_count,
        string_count=string_count,
    )


def sum_size_breakdowns(breakdowns: tuple[SizeBreakdown, ...]) -> SizeBreakdown:
    """Sum multiple :class:`SizeBreakdown`\\ s together (e.g. a bundle's base + splits)."""
    total = breakdowns[0]
    for breakdown in breakdowns[1:]:
        total = total + breakdown
    return total


def sum_dex_infos(infos: tuple[DexInfo, ...]) -> DexInfo:
    """Sum multiple :class:`DexInfo`\\ s together (e.g. a bundle's base + splits)."""
    total = infos[0]
    for info in infos[1:]:
        total = total + info
    return total
