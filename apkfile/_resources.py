"""Resource-table-derived value objects: icons and Android's named screen-density/size buckets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ._apk import ApkFile

__all__ = ["DensityBucket", "Icon", "ScreenSize"]

# Raw dpi values for each named bucket. See
# https://developer.android.com/training/multiscreen/screendensities and androguard's own
# `ACONFIGURATION_DENSITY_*` constants (confirmed hands-on against androguard.core.axml).
_BUCKET_DPI: dict[str, int] = {
    "default": 0,
    "ldpi": 120,
    "mdpi": 160,
    "tvdpi": 213,
    "hdpi": 240,
    "xhdpi": 320,
    "xxhdpi": 480,
    "xxxhdpi": 640,
    "anydpi": 65534,
    "nodpi": 65535,
}
_DPI_TO_BUCKET_NAME: dict[int, str] = {dpi: name for name, dpi in _BUCKET_DPI.items()}


class DensityBucket(str, Enum):
    """
    A named Android screen-density bucket (a resource directory's `-<density>` qualifier, e.g.
    `res/drawable-xhdpi/`).

    See the [screen densities guide](https://developer.android.com/training/multiscreen/screendensities).

    Attributes:
        DEFAULT: No density qualifier at all (0dpi) — matches any density as a last resort.
        LDPI: Low density (120dpi).
        MDPI: Medium density (160dpi) — the baseline.
        TVDPI: TV density (213dpi), an in-between bucket mostly used by 720p TVs.
        HDPI: High density (240dpi).
        XHDPI: Extra-high density (320dpi).
        XXHDPI: Extra-extra-high density (480dpi).
        XXXHDPI: Extra-extra-extra-high density (640dpi).
        ANY: `anydpi` — density-independent (vector drawables, adaptive icons). Takes priority
            over every other bucket when Android resolves which resource to use.
        NONE: `nodpi` — density-independent fallback, used when nothing density-specific matches.
    """

    DEFAULT = "default"
    LDPI = "ldpi"
    MDPI = "mdpi"
    TVDPI = "tvdpi"
    HDPI = "hdpi"
    XHDPI = "xhdpi"
    XXHDPI = "xxhdpi"
    XXXHDPI = "xxxhdpi"
    ANY = "anydpi"
    NONE = "nodpi"

    @property
    def dpi(self) -> int:
        """The raw dpi value this bucket represents (e.g. `320` for `XHDPI`)."""
        return _BUCKET_DPI[self.value]

    @classmethod
    def from_dpi(cls, dpi: int) -> DensityBucket | None:
        """The named bucket for a raw dpi value, or `None` if it isn't one of the standard ones."""
        name = _DPI_TO_BUCKET_NAME.get(dpi)
        return cls(name) if name is not None else None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class ScreenSize(str, Enum):
    """
    A screen size an app declares support for via `<supports-screens>`.

    See the [supports-screens docs](https://developer.android.com/guide/topics/manifest/supports-screens-element).
    """

    SMALL = "small"
    NORMAL = "normal"
    LARGE = "large"
    XLARGE = "xlarge"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


@dataclass(frozen=True, slots=True)
class Icon:
    """
    A single app-icon resource, resolved from `<application android:icon>`.

    >>> icon = max(apk.icons, key=lambda i: i.density)
    >>> icon.extract("icon.png")

    Attributes:
        density: The raw dpi value of this icon's density qualifier.
        bucket: The named density bucket this icon was compiled for (`DensityBucket.ANY` for
            an adaptive icon), if it matches one of the standard values.
        path: The in-archive path to this icon's file (e.g. `"res/mipmap-xxhdpi/ic_launcher.png"`).
            May be an XML file (an [adaptive icon](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive)
            descriptor) rather than a raster image when `bucket` is `DensityBucket.ANY`.
    """

    density: int
    bucket: DensityBucket | None
    path: str
    _apk: ApkFile = field(repr=False, compare=False)

    def read_bytes(self) -> bytes:
        """Read this icon's raw bytes directly out of the apk's archive."""
        with self._apk.as_zip_file() as zf:
            return zf.read(self.path)

    def extract(self, path: str | os.PathLike[str] | None = None) -> None:
        """
        Write this icon's bytes to `path`.

        Args:
            path: Where to write the icon. Defaults to this icon's own filename (the last path
                segment of `self.path`) in the current working directory.
        """
        target = (
            Path(path)
            if path is not None
            else Path.cwd() / PurePosixPath(self.path).name
        )
        logger.debug("Extracting icon {} to {}", self.path, target)
        target.write_bytes(self.read_bytes())
