from __future__ import annotations

from apkfile import ApkFile
from apkfile._signing import SigningScheme


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


def test_certificate_is_expired(test_debug_path: str) -> None:
    apk = ApkFile(test_debug_path)
    (cert,) = apk.signing.certificates[SigningScheme.V1]
    # the debug cert's validity window is 2010-2011.
    assert cert.is_expired() is True
    assert cert.is_expired(cert.not_before) is False
