"""Signature enforcement shared by the FastAPI integrations.

When verification is enabled (any ``MYC_PROFILE_PUBLIC_KEY_*``), every
integration must authenticate the profile before exposing it, in every
``ENVIRONMENT``: the development leniency never applies to a failed signature.

Responses are generic: 403 ``Unable to verify Mycelium profile`` for any
rejection, 500 for configuration or internal errors. The detailed ``reason``
is only logged, without tokens, claims or profile content.
"""

import logging
from typing import Optional, Sequence

from fastapi import HTTPException, Request

from myc_http_tools.exceptions import (
    ProfileSignatureConfigurationError,
    ProfileSignatureError,
)
from myc_http_tools.functions.verify_profile_signature import (
    verify_and_decode_profile,
)
from myc_http_tools.models.profile import Profile
from myc_http_tools.profile_signature_config import (
    ProfileSignatureVerifier,
    get_profile_signature_verifier,
)
from myc_http_tools.settings import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_PROFILE_SIGNATURE_KEY,
)

logger = logging.getLogger(__name__)

REJECTION_DETAIL = "Unable to verify Mycelium profile"

INTERNAL_DETAIL = "Unable to check user identity. Please contact administrators"


def active_verifier() -> Optional[ProfileSignatureVerifier]:
    """Return the verifier, or ``None`` when verification is disabled.

    An invalid configuration fails closed with HTTP 500.
    """
    try:
        return get_profile_signature_verifier()
    except ProfileSignatureConfigurationError as error:
        logger.error(
            "profile_signature.verify outcome=error reason=configuration_invalid "
            "code=%s",
            error.code,
        )
        raise HTTPException(status_code=500, detail=INTERNAL_DETAIL) from error


def _single(values: Sequence[str], missing_reason: str) -> str:
    if len(values) > 1:
        raise ProfileSignatureError("duplicate_header")

    if len(values) == 0 or values[0] == "":
        raise ProfileSignatureError(missing_reason)

    return values[0]


def verified_profile(
    profile_values: Sequence[str],
    signature_values: Sequence[str],
    verifier: ProfileSignatureVerifier,
) -> Profile:
    """Authenticate and decode the profile or raise ``HTTPException``."""
    try:
        profile_header = _single(profile_values, "missing_profile")
        signature_header = _single(signature_values, "missing_signature")
        profile = verify_and_decode_profile(
            profile_header, signature_header, verifier
        )
    except ProfileSignatureError as error:
        logger.warning(
            "profile_signature.verify outcome=rejected reason=%s", error.reason
        )
        raise HTTPException(status_code=403, detail=REJECTION_DETAIL) from error
    except Exception as error:
        logger.error(
            "profile_signature.verify outcome=error reason=internal type=%s",
            type(error).__name__,
        )
        raise HTTPException(status_code=500, detail=INTERNAL_DETAIL) from error

    logger.debug("profile_signature.verify outcome=ok")
    return profile


def header_values_from_request(
    request: Request,
) -> tuple[list[str], list[str]]:
    """All values of both headers, so duplicates can be rejected."""
    return (
        request.headers.getlist(DEFAULT_PROFILE_KEY),
        request.headers.getlist(DEFAULT_PROFILE_SIGNATURE_KEY),
    )


def header_values(
    request: Optional[Request],
    profile_header: Optional[str],
    signature_header: Optional[str],
) -> tuple[list[str], list[str]]:
    """Prefer the full request headers; fall back to scalar arguments.

    The fallback only exists for direct (non-FastAPI) calls of the header
    dependencies, where multiplicity cannot be observed.
    """
    if request is not None:
        return header_values_from_request(request)

    return (
        [] if profile_header is None else [profile_header],
        [] if signature_header is None else [signature_header],
    )
