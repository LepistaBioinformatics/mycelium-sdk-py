"""How long a fetched profile JWKS may be cached.

Reads the ``max-age`` directive of a ``Cache-Control`` value and clamps it to
1 minute..1 day; 12 hours when the header or the directive is absent or
unreadable. Shared rule of the gateway and every SDK (``jwks-vectors.json``).
"""

import re
from typing import Optional

from myc_http_tools.settings import (
    PROFILE_JWKS_DEFAULT_MAX_AGE_SECONDS,
    PROFILE_JWKS_MAX_MAX_AGE_SECONDS,
    PROFILE_JWKS_MIN_MAX_AGE_SECONDS,
)

_UNSIGNED = re.compile(r"^\+?[0-9]+$")
_U64_MAX = 2**64 - 1


def _read_max_age_directive(directive: str) -> Optional[int]:
    name, separator, value = directive.strip().partition("=")
    if separator == "" or name.strip().lower() != "max-age":
        return None

    trimmed = value.strip()
    if not _UNSIGNED.fullmatch(trimmed) or int(trimmed) > _U64_MAX:
        return None

    return int(trimmed)


def read_jwks_cache_max_age(cache_control: Optional[str]) -> int:
    """Cache lifetime in seconds for a ``Cache-Control`` value."""
    announced = None
    for directive in (cache_control or "").split(","):
        announced = _read_max_age_directive(directive)
        if announced is not None:
            break

    if announced is None:
        announced = PROFILE_JWKS_DEFAULT_MAX_AGE_SECONDS

    return min(
        max(announced, PROFILE_JWKS_MIN_MAX_AGE_SECONDS),
        PROFILE_JWKS_MAX_MAX_AGE_SECONDS,
    )
