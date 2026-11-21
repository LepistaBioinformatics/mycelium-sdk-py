"""Read the gateway profile JWKS into the keys a downstream trusts.

Strict and whole-document: one unsafe entry (private member ``d``, another key
type or curve, a key that is not 32 bytes of unpadded Base64URL, a
non-canonical or duplicated ``kid``, a non-signature ``use`` or another
``alg``) refuses the set, so the verifier keeps its last valid one instead of
trusting a partial set. Unknown members are ignored (RFC 7517). Same rules as
the gateway and the other SDKs (``jwks-vectors.json``).
"""

import base64
import binascii
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from myc_http_tools.exceptions import ProfileSignatureConfigurationError
from myc_http_tools.profile_signature_verifier import is_canonical_key_version

_JWKS = "profile JWKS"
_ED25519_PUBLIC_KEY_BYTES = 32
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
_INSTALL_HINT = (
    "Install the optional verification dependencies with: "
    "pip install 'mycelium-http-tools[signature]'"
)


def _invalid(problem: str) -> ProfileSignatureConfigurationError:
    return ProfileSignatureConfigurationError(f"{_JWKS} {problem}")


def require_verification_dependencies(setting: str) -> None:
    """Configuration error when the ``signature`` extra is absent."""
    try:
        import cryptography.hazmat.primitives.asymmetric.ed25519  # noqa: F401
        import jwt  # noqa: F401
    except ImportError as error:
        raise ProfileSignatureConfigurationError(
            f"{setting} is set but verification dependencies are missing. "
            f"{_INSTALL_HINT}"
        ) from error


def _expect_member(
    entry: Mapping[str, Any], name: str, expected: str, required: bool
) -> None:
    if name not in entry and not required:
        return

    value = entry.get(name)
    if not (isinstance(value, str) and value == expected):
        raise _invalid(f"entry member {name} must be {expected}")


def _read_kid(entry: Mapping[str, Any]) -> str:
    kid = entry.get("kid")
    if not (isinstance(kid, str) and is_canonical_key_version(kid)):
        raise _invalid("entry kid must be a canonical positive integer")

    return kid


def _read_x(entry: Mapping[str, Any]) -> bytes:
    x = entry.get("x")
    problem = "entry x must be a 32-byte Base64URL key"
    if not (isinstance(x, str) and _BASE64URL.fullmatch(x)):
        raise _invalid(problem)

    try:
        raw = base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
    except (binascii.Error, ValueError) as error:
        raise _invalid(problem) from error

    canonical = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    if len(raw) != _ED25519_PUBLIC_KEY_BYTES or canonical != x:
        raise _invalid(problem)

    return raw


def read_ed25519_public_jwk(entry: Any) -> tuple[str, bytes]:
    """``(kid, raw public key)`` of one JWK, or a configuration error."""
    if not isinstance(entry, dict):
        raise _invalid("entry is not a JSON object")

    if "d" in entry:
        raise _invalid("entry carries private key material (d)")

    _expect_member(entry, "kty", "OKP", True)
    _expect_member(entry, "crv", "Ed25519", True)
    _expect_member(entry, "use", "sig", False)
    _expect_member(entry, "alg", "EdDSA", False)

    return _read_kid(entry), _read_x(entry)


def _read_entries(document: bytes) -> list:
    try:
        parsed = json.loads(document.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise _invalid("is not JSON") from error

    entries = parsed.get("keys") if isinstance(parsed, dict) else None
    if not isinstance(entries, list) or len(entries) == 0:
        raise _invalid("has no keys array")

    return entries


def trusted_profile_keys_from_jwks(document: bytes) -> Mapping[str, Any]:
    """Parse a JWKS document into a read-only ``kid -> Ed25519PublicKey``."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )

    keys: dict[str, Any] = {}
    for entry in _read_entries(document):
        kid, raw = read_ed25519_public_jwk(entry)
        if kid in keys:
            raise _invalid("has a duplicated kid")

        keys[kid] = Ed25519PublicKey.from_public_bytes(raw)

    return MappingProxyType(keys)
