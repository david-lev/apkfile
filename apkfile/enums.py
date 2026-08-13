"""Small enums used across apkfile."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .abi import Abi

__all__ = ["FormFactor", "InstallLocation", "SplitType"]


class FormFactor(str, Enum):
    """
    A device form factor an app appears to specifically target, inferred from manifest heuristics
    androguard applies (``<uses-feature>``/``<uses-feature required="false">`` declarations). These
    are heuristics, not authoritative — not every app sets the underlying features, even ones that
    do target the form factor.

    Attributes:
        TV: The app doesn't require a touchscreen (the rule Google Play uses for its TV section —
            see `is_androidtv <https://developer.android.com/training/tv/start/start.html>`_), or it
            declares the ``android.software.leanback`` feature (the TV/Leanback UI framework).
        WEARABLE: The app declares the ``android.hardware.type.watch`` feature.
    """

    TV = "tv"
    WEARABLE = "wearable"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class InstallLocation(str, Enum):
    """
    Where the application can be installed: on external storage, internal only, or auto.

    See the `Android documentation <https://developer.android.com/reference/android/content/pm/PackageInfo.html#installLocation>`_.

    Attributes:
        AUTO: Let the system decide where to install the app.
        INTERNAL_ONLY: Install the app on internal storage only.
        PREFER_EXTERNAL: Prefer external storage.
    """

    AUTO = "auto"
    INTERNAL_ONLY = "internalOnly"
    PREFER_EXTERNAL = "preferExternal"

    @classmethod
    def _missing_(cls, value: object) -> InstallLocation:
        # "internalOnly" is the documented default when `android:installLocation` is absent —
        # NOT "auto" — see developer.android.com/guide/topics/manifest/manifest-element#install.
        return cls.INTERNAL_ONLY

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class SplitType(str, Enum):
    """
    The kind of thing a split APK varies by.

    Attributes:
        LANGUAGE: Split by language/locale.
        DPI: Split by screen density.
        ABI: Split by native ABI.
        OTHER: Anything else (e.g. a feature split).
    """

    LANGUAGE = "language"
    DPI = "dpi"
    ABI = "abi"
    OTHER = "other"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


def classify_split(
    split_name: str, langs: Sequence[str], abis: Sequence[Abi]
) -> SplitType:
    """
    Classify a split APK's split name into a :class:`SplitType`, given the langs/abis it was resolved with.

    Args:
        split_name: The raw ``split`` attribute of the split APK's manifest (e.g. ``"config.en"``).
        langs: The langs supported by the split (usually just the split itself, for a language split).
        abis: The ABIs supported by the split (usually just one, for an ABI split).
    """
    tail = split_name.rsplit(".", 1)[-1]
    if tail.endswith("dpi"):
        return SplitType.DPI
    if tail in langs:
        return SplitType.LANGUAGE
    if len(abis) == 1:
        return SplitType.ABI
    return SplitType.OTHER
