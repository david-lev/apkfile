"""APK signing scheme detection and certificate metadata (via androguard)."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from androguard.core.apk import APK as _AndroguardAPK

__all__ = ["Certificate", "SigningInfo", "SigningScheme"]

_DEBUG_CERT_CN = "Android Debug"

# A signing block can be present-but-corrupt on an otherwise-loadable (`is_valid_APK()`) apk —
# e.g. a repacked/hand-edited file with a truncated or tampered v2/v3 signing block. androguard's
# signing-block parsing is struct/offset-based, so it can raise the same class of low-level errors
# `_apk.py`'s `_PARSE_ERRORS` already guards against. Treat an unparseable scheme as "not detected"
# rather than letting `.signing` blow up metadata access on an otherwise-readable apk.
_SIGNATURE_PARSE_ERRORS = (ValueError, struct.error, IndexError, KeyError, EOFError)


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
        canonical_subject: The subject's `canonical, Java-X500Principal-compatible
            <https://docs.oracle.com/en/java/javase/21/docs/api/java.base/javax/security/auth/x500/X500Principal.html#getName(java.lang.String)>`_
            form, if it could be computed. Unlike :attr:`subject`, this is safe to use for identity
            comparisons — two textually-different :attr:`subject` strings can represent the same
            logical name, or vice versa, depending on encoding/whitespace/case.
        canonical_issuer: The issuer's canonical form; see :attr:`canonical_subject`.
        serial_number: The certificate's serial number.
        not_before: The start of the certificate's validity period.
        not_after: The end of the certificate's validity period.
        sha1: The SHA1 fingerprint of the DER-encoded certificate (lowercase hex).
        sha256: The SHA256 fingerprint of the DER-encoded certificate (lowercase hex).
        md5: The MD5 fingerprint of the DER-encoded certificate (lowercase hex).
        public_key_algorithm: The public key's algorithm (e.g. ``"rsa"``, ``"ec"``, ``"dsa"``).
        public_key_bit_size: The public key's size in bits, if it could be computed (e.g. ``2048``
            for a typical RSA key) — a very small size (e.g. RSA below 2048 bits) is a weak-key smell.
        is_self_signed: Whether the certificate's subject and issuer are the same.
        is_debug: Whether this looks like the standard Android SDK debug certificate
            (self-signed, subject common name ``"Android Debug"``).
    """

    subject: str
    issuer: str
    canonical_subject: str | None
    canonical_issuer: str | None
    serial_number: int
    not_before: datetime
    not_after: datetime
    sha1: str
    sha256: str
    md5: str
    public_key_algorithm: str
    public_key_bit_size: int | None
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
        has_duplicate_signature_ids: Whether the APK has multiple v2/v3 signing blocks sharing an
            ID. A verifier normally uses the first and ignores the rest — a discrepancy some tools
            use to smuggle content past one verifier while another sees something different. See
            `androguard#1030 <https://github.com/androguard/androguard/issues/1030>`_.
    """

    schemes: tuple[SigningScheme, ...]
    certificates: dict[SigningScheme, tuple[Certificate, ...]]
    has_duplicate_signature_ids: bool

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


def _canonical_name(apk: _AndroguardAPK, name: Any) -> str | None:
    try:
        return apk.canonical_name(name)
    except Exception:  # noqa: BLE001 - best-effort enrichment, never worth failing signing info over
        return None


def _public_key_info(asn1_cert: Any) -> tuple[str, int | None]:
    public_key = asn1_cert.public_key
    algorithm = public_key.algorithm
    try:
        bit_size = public_key.bit_size
    except Exception:  # noqa: BLE001 - asn1crypto's bit_size can choke on unusual key algorithms
        bit_size = None
    return algorithm, bit_size


def _to_certificate(apk: _AndroguardAPK, asn1_cert: Any) -> Certificate:
    subject = asn1_cert.subject
    issuer = asn1_cert.issuer
    der = asn1_cert.dump()
    is_self_signed = subject.native == issuer.native
    common_name = subject.native.get("common_name")
    public_key_algorithm, public_key_bit_size = _public_key_info(asn1_cert)
    return Certificate(
        subject=subject.human_friendly,
        issuer=issuer.human_friendly,
        canonical_subject=_canonical_name(apk, subject),
        canonical_issuer=_canonical_name(apk, issuer),
        serial_number=asn1_cert.serial_number,
        not_before=asn1_cert.not_valid_before,
        not_after=asn1_cert.not_valid_after,
        sha1=hashlib.sha1(der).hexdigest(),
        sha256=hashlib.sha256(der).hexdigest(),
        md5=hashlib.md5(der).hexdigest(),
        public_key_algorithm=public_key_algorithm,
        public_key_bit_size=public_key_bit_size,
        is_self_signed=is_self_signed,
        is_debug=is_self_signed and common_name == _DEBUG_CERT_CN,
    )


def build_signing_info(apk: _AndroguardAPK) -> SigningInfo:
    """Build a :class:`SigningInfo` by probing every signing scheme androguard supports.

    A scheme whose block is present but unparseable (corrupt/tampered) is treated as not detected,
    rather than raising — see :data:`_SIGNATURE_PARSE_ERRORS`.
    """
    certificates: dict[SigningScheme, tuple[Certificate, ...]] = {}

    try:
        if apk.is_signed_v1():
            certs = tuple(
                _to_certificate(apk, cert)
                for name in apk.get_signature_names()
                if (cert := apk.get_certificate(name)) is not None
            )
            if certs:
                certificates[SigningScheme.V1] = certs
    except _SIGNATURE_PARSE_ERRORS:
        pass

    for scheme, is_signed, get_certs in (
        (SigningScheme.V2, apk.is_signed_v2, apk.get_certificates_v2),
        (SigningScheme.V3, apk.is_signed_v3, apk.get_certificates_v3),
        (SigningScheme.V31, apk.is_signed_v31, apk.get_certificates_v31),
    ):
        try:
            if is_signed():
                certs = tuple(_to_certificate(apk, cert) for cert in get_certs())
                if certs:
                    certificates[scheme] = certs
        except _SIGNATURE_PARSE_ERRORS:
            continue

    try:
        has_duplicate_signature_ids = apk.has_duplicate_apk_signature_ids()
    except _SIGNATURE_PARSE_ERRORS:
        has_duplicate_signature_ids = False

    return SigningInfo(
        schemes=tuple(certificates.keys()),
        certificates=certificates,
        has_duplicate_signature_ids=has_duplicate_signature_ids,
    )
