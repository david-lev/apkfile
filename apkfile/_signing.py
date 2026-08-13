"""APK signing scheme detection and certificate metadata (via androguard)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from androguard.core.apk import APK as _AndroguardAPK

__all__ = ["Certificate", "SigningInfo", "SigningScheme"]

_DEBUG_CERT_CN = "Android Debug"


class SigningScheme(str, Enum):
    """
    An `APK signing scheme <https://source.android.com/docs/security/features/apksigning>`_.

    Attributes:
        V1: JAR signing (``META-INF/*.{RSA,DSA,EC}``).
        V2: APK Signature Scheme v2.
        V3: APK Signature Scheme v3.
        V31: APK Signature Scheme v3.1 (key rotation).
    """

    V1 = "v1"
    V2 = "v2"
    V3 = "v3"
    V31 = "v3.1"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


@dataclass(frozen=True, slots=True)
class Certificate:
    """
    A signing certificate, as recorded in one of an APK's signing blocks.

    Attributes:
        subject: The certificate subject's distinguished name (human-readable).
        issuer: The certificate issuer's distinguished name (human-readable).
        serial_number: The certificate's serial number.
        not_before: The start of the certificate's validity period.
        not_after: The end of the certificate's validity period.
        sha1: The SHA1 fingerprint of the DER-encoded certificate (lowercase hex).
        sha256: The SHA256 fingerprint of the DER-encoded certificate (lowercase hex).
        md5: The MD5 fingerprint of the DER-encoded certificate (lowercase hex).
        is_self_signed: Whether the certificate's subject and issuer are the same.
        is_debug: Whether this looks like the standard Android SDK debug certificate
            (self-signed, subject common name ``"Android Debug"``).
    """

    subject: str
    issuer: str
    serial_number: int
    not_before: datetime
    not_after: datetime
    sha1: str
    sha256: str
    md5: str
    is_self_signed: bool
    is_debug: bool

    def is_expired(self, at: datetime | None = None) -> bool:
        """Whether this certificate is expired at ``at`` (defaults to now)."""
        now = at if at is not None else datetime.now(self.not_after.tzinfo)
        return now > self.not_after


@dataclass(frozen=True, slots=True)
class SigningInfo:
    """
    An APK's signing information across all detected schemes.

    Attributes:
        schemes: The signing schemes detected on the APK.
        certificates: Mapping of signing scheme to the certificate(s) recorded under it.
    """

    schemes: tuple[SigningScheme, ...]
    certificates: dict[SigningScheme, tuple[Certificate, ...]]

    @property
    def is_debug_signed(self) -> bool:
        """Whether any recorded certificate looks like the standard Android debug certificate."""
        return any(
            cert.is_debug for certs in self.certificates.values() for cert in certs
        )

    @property
    def all_certificates(self) -> tuple[Certificate, ...]:
        """All distinct certificates recorded across every scheme (deduplicated by SHA256)."""
        seen: dict[str, Certificate] = {}
        for certs in self.certificates.values():
            for cert in certs:
                seen.setdefault(cert.sha256, cert)
        return tuple(seen.values())


def _to_certificate(asn1_cert: Any) -> Certificate:
    subject = asn1_cert.subject
    issuer = asn1_cert.issuer
    der = asn1_cert.dump()
    is_self_signed = subject.native == issuer.native
    common_name = subject.native.get("common_name")
    return Certificate(
        subject=subject.human_friendly,
        issuer=issuer.human_friendly,
        serial_number=asn1_cert.serial_number,
        not_before=asn1_cert.not_valid_before,
        not_after=asn1_cert.not_valid_after,
        sha1=hashlib.sha1(der).hexdigest(),
        sha256=hashlib.sha256(der).hexdigest(),
        md5=hashlib.md5(der).hexdigest(),
        is_self_signed=is_self_signed,
        is_debug=is_self_signed and common_name == _DEBUG_CERT_CN,
    )


def build_signing_info(apk: _AndroguardAPK) -> SigningInfo:
    """Build a :class:`SigningInfo` by probing every signing scheme androguard supports."""
    certificates: dict[SigningScheme, tuple[Certificate, ...]] = {}

    if apk.is_signed_v1():
        certs = tuple(
            _to_certificate(cert)
            for name in apk.get_signature_names()
            if (cert := apk.get_certificate(name)) is not None
        )
        if certs:
            certificates[SigningScheme.V1] = certs

    for scheme, is_signed, get_certs in (
        (SigningScheme.V2, apk.is_signed_v2, apk.get_certificates_v2),
        (SigningScheme.V3, apk.is_signed_v3, apk.get_certificates_v3),
        (SigningScheme.V31, apk.is_signed_v31, apk.get_certificates_v31),
    ):
        if is_signed():
            certs = tuple(_to_certificate(cert) for cert in get_certs())
            if certs:
                certificates[scheme] = certs

    return SigningInfo(schemes=tuple(certificates.keys()), certificates=certificates)
