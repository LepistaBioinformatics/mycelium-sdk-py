"""One verification pass: the trusted keys at an instant and the rules.

Kept free of configuration and network concerns, so the strict verifier in
``functions.verify_profile_signature`` and the shared contract vectors can use
it directly. The JWKS-backed verifier builds one per request from its cached
keys.
"""

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

_CANONICAL_VERSION = re.compile(r"^[1-9][0-9]*$")
_MAX_KEY_VERSION = 4_294_967_295


@dataclass(frozen=True)
class ProfileSignatureVerifier:
    """Immutable verification settings: trusted keys by ``kid``.

    ``public_keys`` maps the canonical key version (the JWS ``kid``) to an
    ``Ed25519PublicKey``. It is a read-only mapping. ``expected_audience`` is
    optional here so the shared vectors can exercise both cases; a configured
    downstream always has one.
    """

    public_keys: Mapping[str, Any]
    tolerance_seconds: int
    expected_audience: Optional[str] = None


def is_canonical_key_version(raw: str) -> bool:
    """Whether ``raw`` is a canonical positive u32 (no sign/zeros/spaces)."""
    if len(raw) > 10 or not _CANONICAL_VERSION.fullmatch(raw):
        return False

    return int(raw) <= _MAX_KEY_VERSION
