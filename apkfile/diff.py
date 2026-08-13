"""Comparing two ``ApkFile``\\ s."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from ._apk import ApkFile
    from .abi import Abi

__all__ = ["ApkDiff", "diff"]

_T = TypeVar("_T", bound=str)


@dataclass(frozen=True, slots=True)
class ApkDiff:
    """
    The differences between two :class:`~apkfile.ApkFile`\\ s (``a`` compared against ``b``).

    Attributes:
        package_name_changed: Whether ``a`` and ``b`` have different package names.
        version_code_delta: ``b.version_code - a.version_code``.
        version_name_from: ``a``'s version name.
        version_name_to: ``b``'s version name.
        min_sdk_delta: ``b.min_sdk_version - a.min_sdk_version``, if both are set.
        target_sdk_delta: ``b.target_sdk_version - a.target_sdk_version``, if both are set.
        size_delta: ``b.size - a.size``, in bytes.
        permissions_added: Permissions present in ``b`` but not ``a``.
        permissions_removed: Permissions present in ``a`` but not ``b``.
        features_added: Features present in ``b`` but not ``a``.
        features_removed: Features present in ``a`` but not ``b``.
        libraries_added: Libraries present in ``b`` but not ``a``.
        libraries_removed: Libraries present in ``a`` but not ``b``.
        abis_added: ABIs present in ``b`` but not ``a``.
        abis_removed: ABIs present in ``a`` but not ``b``.
        langs_added: Locales present in ``b`` but not ``a``.
        langs_removed: Locales present in ``a`` but not ``b``.
        signing_changed: Whether ``a`` and ``b`` have no certificate (SHA256) in common. ``None`` if either
            side has no signing information at all.
    """

    package_name_changed: bool
    version_code_delta: int
    version_name_from: str | None
    version_name_to: str | None
    min_sdk_delta: int | None
    target_sdk_delta: int | None
    size_delta: int
    permissions_added: tuple[str, ...]
    permissions_removed: tuple[str, ...]
    features_added: tuple[str, ...]
    features_removed: tuple[str, ...]
    libraries_added: tuple[str, ...]
    libraries_removed: tuple[str, ...]
    abis_added: tuple[Abi, ...]
    abis_removed: tuple[Abi, ...]
    langs_added: tuple[str, ...]
    langs_removed: tuple[str, ...]
    signing_changed: bool | None


def _added(a: Sequence[_T], b: Sequence[_T]) -> tuple[_T, ...]:
    return tuple(sorted(set(b) - set(a)))


def _removed(a: Sequence[_T], b: Sequence[_T]) -> tuple[_T, ...]:
    return tuple(sorted(set(a) - set(b)))


def diff(a: ApkFile, b: ApkFile) -> ApkDiff:
    """
    Compare two :class:`~apkfile.ApkFile`\\ s.

    >>> diff(old_apk, new_apk).permissions_added
    ('android.permission.CAMERA',)

    Args:
        a: The "old"/baseline apk.
        b: The "new" apk to compare against ``a``.
    """
    min_sdk_delta = (
        b.min_sdk_version - a.min_sdk_version
        if a.min_sdk_version is not None and b.min_sdk_version is not None
        else None
    )
    target_sdk_delta = (
        b.target_sdk_version - a.target_sdk_version
        if a.target_sdk_version is not None and b.target_sdk_version is not None
        else None
    )

    a_certs = {cert.sha256 for cert in a.signing.all_certificates}
    b_certs = {cert.sha256 for cert in b.signing.all_certificates}
    signing_changed = (
        None if not a_certs or not b_certs else a_certs.isdisjoint(b_certs)
    )

    return ApkDiff(
        package_name_changed=a.package_name != b.package_name,
        version_code_delta=b.version_code - a.version_code,
        version_name_from=a.version_name,
        version_name_to=b.version_name,
        min_sdk_delta=min_sdk_delta,
        target_sdk_delta=target_sdk_delta,
        size_delta=b.size - a.size,
        permissions_added=_added(a.permissions, b.permissions),
        permissions_removed=_removed(a.permissions, b.permissions),
        features_added=_added(a.features, b.features),
        features_removed=_removed(a.features, b.features),
        libraries_added=_added(a.libraries, b.libraries),
        libraries_removed=_removed(a.libraries, b.libraries),
        abis_added=_added(a.abis, b.abis),
        abis_removed=_removed(a.abis, b.abis),
        langs_added=_added(a.langs, b.langs),
        langs_removed=_removed(a.langs, b.langs),
        signing_changed=signing_changed,
    )
