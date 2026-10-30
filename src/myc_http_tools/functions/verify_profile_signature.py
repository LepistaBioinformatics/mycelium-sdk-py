"""Strict, local verification of the downstream profile signature.

Contract (shared with the gateway and the JavaScript SDK):

- ``x-mycelium-profile-signature`` is a compact JWS, ``alg: EdDSA``, with the
  key version as ``kid`` in the protected header;
- claims ``{iat, ph, aud}``: ``ph`` is the unpadded Base64URL SHA-256 of the
  exact ``x-mycelium-profile`` value; ``iat`` is checked against a symmetric,
  inclusive tolerance window; ``aud`` is compared only when an expected
  audience is configured.

Checks run in a fixed precedence so every SDK reports the same ``reason``.
The profile is only decoded after the signature, claims, time window and hash
are accepted. No network, file or environment access happens here.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Optional

from myc_http_tools.exceptions import ProfileDecodingError, ProfileSignatureError
from myc_http_tools.functions.decode_and_decompress_profile_from_base64 import (
    decode_and_decompress_profile_from_base64_robust,
)
from myc_http_tools.models.profile import Profile
from myc_http_tools.profile_signature_config import (
    ProfileSignatureVerifier,
    is_canonical_key_version,
)
from myc_http_tools.settings import (
    MAX_PROFILE_SIGNATURE_BYTES,
    MAX_SAFE_TIMESTAMP_SECONDS,
)

_FORBIDDEN_HEADER_MEMBERS = ("crit", "b64", "jku", "jwk", "x5u", "x5c")
_ENCODED_DIGEST_LENGTH = 43


def _reject(reason: str) -> ProfileSignatureError:
    return ProfileSignatureError(reason)


def _decode_segment(segment: str) -> Optional[dict]:
    try:
        padded = segment + "=" * (-len(segment) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        return None

    return value if isinstance(value, dict) else None


def _split_token(signature_header: str) -> list[str]:
    if signature_header == "":
        raise _reject("missing_signature")

    oversized = len(signature_header.encode("utf-8")) > MAX_PROFILE_SIGNATURE_BYTES
    parts = signature_header.split(".")
    if oversized or len(parts) != 3:
        raise _reject("malformed_signature")

    return parts


def _select_key(header: dict, verifier: ProfileSignatureVerifier) -> Any:
    if header.get("alg") != "EdDSA":
        raise _reject("unsupported_algorithm")

    if any(member in header for member in _FORBIDDEN_HEADER_MEMBERS):
        raise _reject("malformed_signature")

    kid = header.get("kid")
    is_known = (
        isinstance(kid, str)
        and is_canonical_key_version(kid)
        and kid in verifier.public_keys
    )
    if not is_known:
        raise _reject("unknown_key")

    return verifier.public_keys[kid]


def _verify_jws(signature_header: str, key: Any) -> bytes:
    import jwt

    try:
        return jwt.api_jws.PyJWS().decode(
            signature_header, key=key, algorithms=["EdDSA"]
        )
    except jwt.exceptions.InvalidSignatureError as error:
        raise _reject("invalid_signature") from error
    except jwt.exceptions.InvalidTokenError as error:
        raise _reject("malformed_signature") from error


def _is_safe_timestamp(value: Any) -> bool:
    return (
        type(value) is int and 0 <= value <= MAX_SAFE_TIMESTAMP_SECONDS
    )


def _is_canonical_hash(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != _ENCODED_DIGEST_LENGTH:
        return False

    try:
        raw = base64.urlsafe_b64decode((value + "=").encode("ascii"))
    except (ValueError, UnicodeError):
        return False

    return len(raw) == 32 and _encode_hash(raw) == value


def _encode_hash(digest: bytes) -> str:
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _parse_claims(payload: bytes) -> dict:
    try:
        claims = json.loads(payload)
    except (ValueError, UnicodeError) as error:
        raise _reject("invalid_claims") from error

    is_valid = (
        isinstance(claims, dict)
        and _is_safe_timestamp(claims.get("iat"))
        and _is_canonical_hash(claims.get("ph"))
        and isinstance(claims.get("aud"), str)
        and claims["aud"].strip() != ""
    )
    if not is_valid:
        raise _reject("invalid_claims")

    return claims


def _resolve_now(now_seconds: Optional[int]) -> int:
    now = int(time.time()) if now_seconds is None else now_seconds
    if not _is_safe_timestamp(now):
        raise ValueError("Verifier clock is outside the safe integer range")

    return now


def profile_header_hash(profile_header: str) -> str:
    """Unpadded Base64URL SHA-256 of the exact profile header value."""
    return _encode_hash(hashlib.sha256(profile_header.encode("utf-8")).digest())


def _check_claims(
    claims: dict,
    profile_header: str,
    verifier: ProfileSignatureVerifier,
    now: int,
) -> None:
    if abs(now - claims["iat"]) > verifier.tolerance_seconds:
        raise _reject("timestamp_out_of_tolerance")

    if not hmac.compare_digest(claims["ph"], profile_header_hash(profile_header)):
        raise _reject("profile_hash_mismatch")

    expected = verifier.expected_audience
    if expected is not None and claims["aud"] != expected:
        raise _reject("audience_mismatch")


def verify_profile_signature(
    profile_header: str,
    signature_header: str,
    verifier: ProfileSignatureVerifier,
    *,
    now_seconds: Optional[int] = None,
) -> None:
    """Verify that ``signature_header`` authenticates ``profile_header``.

    Raises ``ProfileSignatureError`` with a stable ``reason`` on rejection.
    Raises ``ValueError`` for an invalid verifier clock (internal error).
    Does not decode the profile; see ``verify_and_decode_profile``.
    """
    if profile_header == "":
        raise _reject("missing_profile")

    parts = _split_token(signature_header)
    header = _decode_segment(parts[0])
    if header is None:
        raise _reject("malformed_signature")

    key = _select_key(header, verifier)
    payload = _verify_jws(signature_header, key)
    claims = _parse_claims(payload)
    _check_claims(claims, profile_header, verifier, _resolve_now(now_seconds))


def verify_and_decode_profile(
    profile_header: str,
    signature_header: str,
    verifier: ProfileSignatureVerifier,
    *,
    now_seconds: Optional[int] = None,
) -> Profile:
    """Verify the signature, then decode the profile (``invalid_profile``)."""
    verify_profile_signature(
        profile_header, signature_header, verifier, now_seconds=now_seconds
    )

    try:
        return decode_and_decompress_profile_from_base64_robust(profile_header)
    except (ProfileDecodingError, ValueError, TypeError) as error:
        raise _reject("invalid_profile") from error
