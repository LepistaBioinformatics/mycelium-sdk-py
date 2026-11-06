"""Where a downstream verifier fetches the gateway profile JWKS.

The location comes only from the service configuration, never from a request:
a verifier that followed a URL found in the message it verifies would let an
attacker choose the keys. ``https://`` is required; ``http://`` is accepted
only with the explicit development switch.
"""

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

from myc_http_tools.exceptions import ProfileSignatureConfigurationError
from myc_http_tools.settings import PROFILE_JWKS_URL_ENV

logger = logging.getLogger(__name__)


def _invalid(problem: str) -> ProfileSignatureConfigurationError:
    return ProfileSignatureConfigurationError(
        f"{PROFILE_JWKS_URL_ENV} {problem}"
    )


@dataclass(frozen=True)
class ProfileJwksUrl:
    value: str

    @classmethod
    def parse(cls, raw: str, allow_insecure_http: bool) -> "ProfileJwksUrl":
        trimmed = raw.strip()
        try:
            parts = urlsplit(trimmed)
            has_credentials = (
                parts.username is not None or parts.password is not None
            )
        except ValueError as error:
            raise _invalid("is not an absolute URL") from error

        if parts.scheme == "" or parts.hostname is None:
            raise _invalid("is not an absolute URL")

        if has_credentials:
            raise _invalid("must not carry credentials")

        if parts.scheme == "https":
            return cls(trimmed)

        if parts.scheme == "http" and allow_insecure_http:
            logger.warning(
                "profile_signature.jwks %s uses plain HTTP; development only",
                PROFILE_JWKS_URL_ENV,
            )
            return cls(trimmed)

        raise _invalid("must use https")
