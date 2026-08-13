from __future__ import annotations

import struct

from apkfile import ApkFile
from apkfile._signing import SigningScheme, build_signing_info


def test_debug_apk_is_debug_signed(test_debug_path: str) -> None:
    apk = ApkFile(test_debug_path)
    signing = apk.signing
    assert signing.schemes == (SigningScheme.V1,)
    assert signing.is_debug_signed is True
    (cert,) = signing.certificates[SigningScheme.V1]
    assert cert.is_self_signed is True
    assert cert.is_debug is True
    assert "Android Debug" in cert.subject
    assert len(cert.sha256) == 64
    assert len(cert.sha1) == 40
    assert len(cert.md5) == 32


def test_release_apk_is_not_debug_signed(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    signing = apk.signing
    assert signing.schemes == (SigningScheme.V1,)
    assert signing.is_debug_signed is False
    (cert,) = signing.certificates[SigningScheme.V1]
    assert cert.is_self_signed is True
    assert cert.is_debug is False
    assert cert.is_expired() is False


def test_all_certificates_dedupes_across_schemes(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    assert len(apk.signing.all_certificates) == 1


def test_certificate_public_key_and_canonical_names(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    (cert,) = apk.signing.certificates[SigningScheme.V1]
    assert cert.public_key_algorithm == "rsa"
    assert cert.public_key_bit_size == 4096
    assert cert.canonical_subject is not None
    assert cert.canonical_subject == cert.canonical_issuer  # self-signed
    assert "hans-christoph steiner" in cert.canonical_subject


def test_signing_info_has_no_duplicate_signature_ids(politedroid_path: str) -> None:
    apk = ApkFile(politedroid_path)
    assert apk.signing.has_duplicate_signature_ids is False


def test_certificate_is_expired(test_debug_path: str) -> None:
    apk = ApkFile(test_debug_path)
    (cert,) = apk.signing.certificates[SigningScheme.V1]
    # the debug cert's validity window is 2010-2011.
    assert cert.is_expired() is True
    assert cert.is_expired(cert.not_before) is False


def test_corrupt_v2_signing_block_is_skipped_not_raised(
    mocker, test_debug_path: str
) -> None:
    apk = ApkFile(test_debug_path)
    # simulate a tampered/truncated v2 signing block: androguard would raise a low-level
    # struct-parsing error rather than return cleanly.
    mocker.patch.object(apk._apk, "is_signed_v2", return_value=True)
    mocker.patch.object(
        apk._apk,
        "get_certificates_v2",
        side_effect=struct.error("unpack requires more data"),
    )
    signing = build_signing_info(apk._apk)
    # v2 is skipped (unparseable); v1 (unaffected) is still reported.
    assert SigningScheme.V2 not in signing.schemes
    assert SigningScheme.V1 in signing.schemes


def test_corrupt_v1_signature_is_skipped_not_raised(
    mocker, test_debug_path: str
) -> None:
    apk = ApkFile(test_debug_path)
    mocker.patch.object(apk._apk, "is_signed_v1", return_value=True)
    mocker.patch.object(
        apk._apk,
        "get_signature_names",
        side_effect=ValueError("corrupt signature file"),
    )
    signing = build_signing_info(apk._apk)
    assert signing.schemes == ()
