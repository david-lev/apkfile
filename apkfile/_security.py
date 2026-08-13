"""Manifest security posture: permissions, exported components, deep links (via androguard)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from androguard.core.apk import APK as _AndroguardAPK

    from ._apk import _XmlElement

__all__ = [
    "ComponentType",
    "DeepLink",
    "ExportedComponent",
    "PermissionInfo",
    "ProtectionLevel",
    "SecurityInfo",
]

_ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
_MIN_CLEARTEXT_DEFAULT_FALSE_SDK = 28
_VIEW_ACTION = "android.intent.action.VIEW"
_COMPONENT_TAGS = ("activity", "activity-alias", "service", "receiver", "provider")


class ProtectionLevel(str, Enum):
    """
    A permission's `protection level <https://developer.android.com/guide/topics/manifest/permission-element#plevel>`_.

    Attributes:
        NORMAL: Low-risk; granted automatically.
        DANGEROUS: Grants the requesting app access to private user data; requires user approval.
        SIGNATURE: Granted only to apps signed with the same certificate as the app that declared it.
        SIGNATURE_OR_SYSTEM: Like ``SIGNATURE``, but also granted to apps in the Android system image.
        UNKNOWN: A protection level apkfile doesn't recognize (e.g. a compound OEM-specific value).
    """

    NORMAL = "normal"
    DANGEROUS = "dangerous"
    SIGNATURE = "signature"
    SIGNATURE_OR_SYSTEM = "signatureOrSystem"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> ProtectionLevel:
        return cls.UNKNOWN

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class ComponentType(str, Enum):
    """
    The kind of manifest component an :class:`ExportedComponent` is.

    Attributes:
        ACTIVITY: An ``<activity>`` or ``<activity-alias>``.
        SERVICE: A ``<service>``.
        RECEIVER: A ``<receiver>``.
        PROVIDER: A ``<provider>``.
    """

    ACTIVITY = "activity"
    SERVICE = "service"
    RECEIVER = "receiver"
    PROVIDER = "provider"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


@dataclass(frozen=True, slots=True)
class PermissionInfo:
    """
    A permission requested by the app, with AOSP-known details if available.

    Attributes:
        name: The fully-qualified permission name (e.g. ``"android.permission.READ_CALENDAR"``).
        protection_level: The permission's protection level, if apkfile recognizes it (``None`` for
            custom/third-party permissions AOSP doesn't document).
        group: The permission group it belongs to, if known.
        label: A short human-readable label, if known.
        description: A longer human-readable description, if known.
    """

    name: str
    protection_level: ProtectionLevel | None
    group: str | None
    label: str | None
    description: str | None

    @property
    def is_dangerous(self) -> bool:
        """Whether this permission's protection level is :attr:`ProtectionLevel.DANGEROUS`."""
        return self.protection_level is ProtectionLevel.DANGEROUS


@dataclass(frozen=True, slots=True)
class ExportedComponent:
    """
    A manifest component (activity/service/receiver/provider) and its exported status.

    Attributes:
        name: The component's fully-qualified class name.
        type: What kind of component this is.
        exported: Whether the component is reachable from other apps — either explicitly declared via
            ``android:exported``, or (pre-Android-12 default) implied by having an ``<intent-filter>``.
        permission: The permission another app must hold to interact with this component, if any.
        has_intent_filter: Whether the component declares at least one ``<intent-filter>``.
    """

    name: str
    type: ComponentType
    exported: bool
    permission: str | None
    has_intent_filter: bool


@dataclass(frozen=True, slots=True)
class DeepLink:
    """
    A deep link into an activity, resolved from an ``<intent-filter>``'s ``VIEW`` action + ``<data>``.

    Attributes:
        activity: The fully-qualified name of the activity this deep link opens.
        scheme: The URI scheme (e.g. ``"https"``), if declared.
        host: The URI host, if declared.
        path: The exact URI path, if declared.
        path_prefix: The URI path prefix, if declared.
        path_pattern: The URI path pattern, if declared.
        mime_type: The MIME type this deep link accepts, if declared.
    """

    activity: str
    scheme: str | None
    host: str | None
    path: str | None
    path_prefix: str | None
    path_pattern: str | None
    mime_type: str | None


@dataclass(frozen=True, slots=True)
class SecurityInfo:
    """
    An APK's security-relevant manifest posture.

    Attributes:
        debuggable: Whether ``android:debuggable`` is set on ``<application>``.
        allow_backup: Whether the app allows its data to be backed up (defaults to ``True`` when unset,
            matching the Android platform default).
        uses_cleartext_traffic: Whether the app permits plaintext (non-TLS) network traffic. ``None`` means
            the manifest doesn't declare it explicitly; the effective platform default is ``False`` from
            ``target_sdk_version`` 28 onward, and ``True`` before that.
        has_network_security_config: Whether the app ships a `Network Security Config
            <https://developer.android.com/privacy-and-security/security-config>`_
            (``android:networkSecurityConfig``), which can further restrict cleartext traffic per-domain.
        permissions: Every requested permission, with AOSP details where available.
        dangerous_permissions: The subset of :attr:`permissions` classified as
            :attr:`ProtectionLevel.DANGEROUS` (names only).
        exported_components: Every activity/service/receiver/provider and its exported status.
        unprotected_exported_components: The subset of :attr:`exported_components` that are exported and
            require no permission to interact with — the most actionable manifest security finding.
        deep_links: Deep links resolved from activities' ``VIEW`` intent filters.
    """

    debuggable: bool
    allow_backup: bool
    uses_cleartext_traffic: bool | None
    has_network_security_config: bool
    permissions: tuple[PermissionInfo, ...]
    dangerous_permissions: tuple[str, ...]
    exported_components: tuple[ExportedComponent, ...]
    unprotected_exported_components: tuple[ExportedComponent, ...]
    deep_links: tuple[DeepLink, ...]

    def effective_uses_cleartext_traffic(self, target_sdk_version: int | None) -> bool:
        """Resolve :attr:`uses_cleartext_traffic` to its effective value given ``target_sdk_version``."""
        if self.uses_cleartext_traffic is not None:
            return self.uses_cleartext_traffic
        return (
            target_sdk_version is None
            or target_sdk_version < _MIN_CLEARTEXT_DEFAULT_FALSE_SDK
        )


def _qualify(name: str, package: str) -> str:
    dot = name.find(".")
    if dot == 0:
        return package + name
    if dot == -1:
        return f"{package}.{name}"
    return name


def _bool_attr(element: _XmlElement, attr: str) -> bool | None:
    value = element.get(_ANDROID_NS + attr)
    return None if value is None else value == "true"


def _build_permissions(apk: _AndroguardAPK) -> tuple[PermissionInfo, ...]:
    # androguard's own type hints declare `dict[str, list[str]]` for both of these, but they
    # actually return `dict[str, dict[str, str]]` at runtime (confirmed hands-on).
    details: dict[str, dict[str, Any]] = {}
    details.update(apk.get_declared_permissions_details())  # ty: ignore[no-matching-overload]
    details.update(apk.get_requested_aosp_permissions_details())  # ty: ignore[no-matching-overload]
    infos: list[PermissionInfo] = []
    for name in apk.get_permissions():
        detail = details.get(name)
        if detail is None:
            infos.append(
                PermissionInfo(
                    name=name,
                    protection_level=None,
                    group=None,
                    label=None,
                    description=None,
                )
            )
            continue
        level = detail.get("protectionLevel")
        infos.append(
            PermissionInfo(
                name=name,
                protection_level=ProtectionLevel(level) if level else None,
                group=detail.get("permissionGroup"),
                label=detail.get("label"),
                description=detail.get("description"),
            )
        )
    return tuple(infos)


def _build_exported_components(
    manifest_root: _XmlElement, package: str
) -> tuple[ExportedComponent, ...]:
    components: list[ExportedComponent] = []
    for tag in _COMPONENT_TAGS:
        component_type = (
            ComponentType.ACTIVITY if tag.startswith("activity") else ComponentType(tag)
        )
        for element in manifest_root.iter(tag):
            raw_name = element.get(_ANDROID_NS + "name")
            if not raw_name:
                continue
            has_intent_filter = element.find("intent-filter") is not None
            explicit_exported = _bool_attr(element, "exported")
            exported = (
                explicit_exported
                if explicit_exported is not None
                else has_intent_filter
            )
            components.append(
                ExportedComponent(
                    name=_qualify(raw_name, package),
                    type=component_type,
                    exported=exported,
                    permission=element.get(_ANDROID_NS + "permission"),
                    has_intent_filter=has_intent_filter,
                )
            )
    return tuple(components)


def _build_deep_links(
    apk: _AndroguardAPK, manifest_root: _XmlElement, package: str
) -> tuple[DeepLink, ...]:
    deep_links: list[DeepLink] = []
    for tag in ("activity", "activity-alias"):
        for element in manifest_root.iter(tag):
            raw_name = element.get(_ANDROID_NS + "name")
            if not raw_name or element.find("intent-filter") is None:
                continue
            name = _qualify(raw_name, package)
            filters = apk.get_intent_filters(tag, name)
            if _VIEW_ACTION not in filters.get("action", ()):
                continue
            # androguard's type hint declares `data` as `list[str]`, but it's actually
            # `list[dict[str, str]]` at runtime (confirmed hands-on) — see its docstring.
            for raw_data in filters.get("data", ()):
                data = cast("dict[str, str]", raw_data)
                deep_links.append(
                    DeepLink(
                        activity=name,
                        scheme=data.get("scheme"),
                        host=data.get("host"),
                        path=data.get("path"),
                        path_prefix=data.get("pathPrefix"),
                        path_pattern=data.get("pathPattern"),
                        mime_type=data.get("mimeType"),
                    )
                )
    return tuple(deep_links)


def build_security_info(
    apk: _AndroguardAPK, manifest_root: _XmlElement
) -> SecurityInfo:
    """Build a :class:`SecurityInfo` from an androguard ``APK`` and its parsed manifest root."""
    package = apk.get_package()
    application = manifest_root.find("application")

    debuggable = (
        bool(_bool_attr(application, "debuggable"))
        if application is not None
        else False
    )
    allow_backup = (
        _bool_attr(application, "allowBackup") if application is not None else None
    )
    uses_cleartext_traffic = (
        _bool_attr(application, "usesCleartextTraffic")
        if application is not None
        else None
    )
    has_network_security_config = (
        application is not None
        and application.get(_ANDROID_NS + "networkSecurityConfig") is not None
    )

    permissions = _build_permissions(apk)
    exported_components = _build_exported_components(manifest_root, package)

    return SecurityInfo(
        debuggable=debuggable,
        allow_backup=True if allow_backup is None else allow_backup,
        uses_cleartext_traffic=uses_cleartext_traffic,
        has_network_security_config=has_network_security_config,
        permissions=permissions,
        dangerous_permissions=tuple(p.name for p in permissions if p.is_dangerous),
        exported_components=exported_components,
        unprotected_exported_components=tuple(
            c for c in exported_components if c.exported and c.permission is None
        ),
        deep_links=_build_deep_links(apk, manifest_root, package),
    )
