"""Where a downstream verifier fetches the gateway profile JWKS.

The location comes only from the service configuration, never from a request:
a verifier that followed a URL found in the message it verifies would let an
attacker choose the keys. ``https://`` is required; ``http://`` is accepted
only with the explicit development switch.

Two forms are accepted, so a service only needs to know where its gateway is:

- the complete endpoint, ending in ``PROFILE_JWKS_PATH``, used as is;
- the gateway base (``mycelium.example.com``, ``https://host/prefix``), to
  which ``PROFILE_JWKS_PATH`` is appended. Without a scheme, ``https://`` is
  assumed.
"""

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

from myc_http_tools.exceptions import ProfileSignatureConfigurationError
from myc_http_tools.settings import PROFILE_JWKS_PATH, PROFILE_JWKS_URL_ENV

logger = logging.getLogger(__name__)


def _invalid(problem: str) -> ProfileSignatureConfigurationError:
    return ProfileSignatureConfigurationError(
        f"{PROFILE_JWKS_URL_ENV} {problem}"
    )


def _with_default_scheme(configured: str) -> str:
    if "://" in configured:
        return configured

    if configured == "" or configured.startswith("/"):
        raise _invalid("is not an absolute URL")

    return f"https://{configured}"


@dataclass(frozen=True)
class ProfileJwksUrl:
    value: str

    @classmethod
    def parse(cls, raw: str, allow_insecure_http: bool) -> "ProfileJwksUrl":
        configured = _with_default_scheme(raw.strip())
        try:
            parts = urlsplit(configured)
            has_credentials = (
                parts.username is not None or parts.password is not None
            )
            parts.port
        except ValueError as error:
            raise _invalid("is not an absolute URL") from error

        if parts.scheme == "" or parts.hostname is None:
            raise _invalid("is not an absolute URL")

        if has_credentials:
            raise _invalid("must not carry credentials")

        if parts.scheme == "http" and allow_insecure_http:
            logger.warning(
                "profile_signature.jwks %s uses plain HTTP; development only",
                PROFILE_JWKS_URL_ENV,
            )
        elif parts.scheme != "https":
            raise _invalid("must use https")

        if parts.path.endswith(PROFILE_JWKS_PATH):
            return cls(configured)

        if "?" in configured or "#" in configured:
            raise _invalid("must not carry a query or fragment")

        return cls(f"{configured.rstrip('/')}{PROFILE_JWKS_PATH}")
