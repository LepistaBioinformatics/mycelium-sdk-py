"""FastAPI middleware for extracting profile from HTTP headers.

This module provides middleware and dependencies for extracting user profiles
from HTTP headers in FastAPI applications. The profile is expected to be
Base64-encoded and ZSTD-compressed in the 'x-mycelium-profile' header.

Signature verification: when ``MYCELIUM_JWKS_URL`` is configured, all four
entry points verify ``x-mycelium-profile-signature`` with the keys published
by the gateway before decoding, and reject failures with 403 in every
environment (see ``enforce_profile_signature``). Without that configuration
the behavior below is unchanged, and a signed profile logs one warning.
"""

import logging
import os
from typing import Optional

from myc_http_tools.exceptions import ProfileDecodingError
from myc_http_tools.functions import decode_and_decompress_profile_from_base64
from myc_http_tools.models.profile import Profile
from myc_http_tools.settings import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_PROFILE_SIGNATURE_KEY,
)

try:
    from fastapi import HTTPException, Request, Header
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool
    from typing import Annotated

    from myc_http_tools.fastapi.enforce_profile_signature import (
        active_verifier,
        header_values,
        header_values_from_request,
        note_unverified_signature,
        verified_profile,
    )

    FASTAPI_AVAILABLE = True
except ImportError:
    # FastAPI not available - define placeholder types
    FASTAPI_AVAILABLE = False

    class Request:  # type: ignore[no-redef]
        """Placeholder for Request when FastAPI is not available."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "FastAPI dependencies not installed. "
                "Install with: pip install mycelium-http-tools[fastapi]"
            )

    class HTTPException(Exception):  # type: ignore[no-redef]
        """Placeholder for HTTPException when FastAPI is not available."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "FastAPI dependencies not installed. "
                "Install with: pip install mycelium-http-tools[fastapi]"
            )

    class JSONResponse:  # type: ignore[no-redef]
        """Placeholder for JSONResponse when FastAPI is not available."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "FastAPI dependencies not installed. "
                "Install with: pip install mycelium-http-tools[fastapi]"
            )

    class Header:  # type: ignore[no-redef]
        """Placeholder for Header when FastAPI is not available."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "FastAPI dependencies not installed. "
                "Install with: pip install mycelium-http-tools[fastapi]"
            )

    def Annotated(*args, **kwargs):  # type: ignore[misc]
        """Placeholder for Annotated when FastAPI is not available."""
        raise ImportError(
            "FastAPI dependencies not installed. "
            "Install with: pip install mycelium-http-tools[fastapi]"
        )


logger = logging.getLogger(__name__)


def get_profile_from_request(request: Request) -> Optional[Profile]:
    """Extract profile from HTTP headers.

    This function extracts the profile from the 'x-mycelium-profile' header
    in the HTTP request. The header should contain a Base64-encoded,
    ZSTD-compressed profile.

    Args:
        request: The FastAPI Request object

    Returns:
        Profile object if successfully parsed, None if in development mode
        and header is missing

    Raises:
        HTTPException: If required header is missing in production environment
        or if the decoding/decompression fails
        ImportError: If FastAPI dependencies are not installed
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI dependencies not installed. "
            "Install with: pip install mycelium-http-tools[fastapi]"
        )

    verifier = active_verifier()
    profile_values, signature_values = header_values_from_request(request)
    if verifier is not None:
        return verified_profile(profile_values, signature_values, verifier)

    note_unverified_signature(signature_values)
    environment = os.getenv("ENVIRONMENT", "development")
    incoming_headers = dict(request.headers)

    if environment != "development":
        if DEFAULT_PROFILE_KEY not in incoming_headers:
            raise HTTPException(
                status_code=403,
                detail=f"Required header '{DEFAULT_PROFILE_KEY}' missing in production environment.",
            )

        try:
            # Decode and decompress the profile from Base64/ZSTD
            return decode_and_decompress_profile_from_base64(
                incoming_headers[DEFAULT_PROFILE_KEY]
            )
        except ProfileDecodingError as e:
            logger.warning(
                f"Unable to decode and decompress profile: {e.message}"
            )
            raise HTTPException(
                status_code=401,
                detail="Unable to check user identity. Please contact administrators",
            )
        except Exception as e:
            logger.warning(f"Unable to check user identity due: {e}")
            raise HTTPException(
                status_code=401,
                detail="Unable to check user identity. Please contact administrators",
            )

    # In development mode, try to parse if header exists, otherwise return None
    if DEFAULT_PROFILE_KEY in incoming_headers:
        try:
            return decode_and_decompress_profile_from_base64(
                incoming_headers[DEFAULT_PROFILE_KEY]
            )
        except Exception as e:
            # In development, we're more lenient with errors
            logger.debug(f"Failed to decode profile in development mode: {e}")
            return None

    return None


async def profile_middleware(request: Request, call_next):
    """FastAPI middleware to extract and attach profile to request state.

    This middleware extracts the profile from the 'x-mycelium-profile' header
    and attaches it to the request state for easy access in route handlers.

    Usage:
        app.add_middleware(BaseHTTPMiddleware, dispatch=profile_middleware)

    Then in your route handlers:
        profile = request.state.profile

    Raises:
        ImportError: If FastAPI dependencies are not installed
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI dependencies not installed. "
            "Install with: pip install mycelium-http-tools[fastapi]"
        )

    signature_enabled, signature_rejection = (
        await _enforce_signature_in_middleware(request)
    )
    if signature_rejection is not None:
        return signature_rejection

    if signature_enabled:
        return await call_next(request)

    try:
        profile = get_profile_from_request(request)
        request.state.profile = profile
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        # Handle any other unexpected errors
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(e)}"},
        )

    response = await call_next(request)
    return response


async def _enforce_signature_in_middleware(request: Request):
    """Verify when enabled: ``(enabled, rejection_response_or_None)``.

    On success the verified profile is stored in ``request.state.profile``.
    A response (not an exception) is returned on failure: exceptions raised
    from an HTTP middleware bypass FastAPI's exception handlers. The
    verification runs in a worker thread: it may fetch the gateway JWKS.
    """
    try:
        verifier = active_verifier()
        profile_values, signature_values = header_values_from_request(request)
        if verifier is None:
            note_unverified_signature(signature_values)
            return False, None

        request.state.profile = await run_in_threadpool(
            verified_profile, profile_values, signature_values, verifier
        )
    except HTTPException as error:
        return True, JSONResponse(
            status_code=error.status_code, content={"detail": error.detail}
        )

    return True, None


def get_profile_from_header(
    profile_header: Annotated[
        str | None, Header(alias="x-mycelium-profile")
    ] = None,
    signature_header: Annotated[
        str | None, Header(alias=DEFAULT_PROFILE_SIGNATURE_KEY)
    ] = None,
    request: Request = None,
) -> Profile | None:
    """FastAPI dependency to extract profile from x-mycelium-profile header.

    This function can be used as a FastAPI dependency to automatically extract
    and parse the profile from the HTTP header. The header should contain a
    Base64-encoded, ZSTD-compressed profile.

    Args:
        profile_header: The Base64-encoded, ZSTD-compressed profile string

    Returns:
        Profile object if successfully parsed, None if header is missing or invalid

    Raises:
        HTTPException: If required header is missing in production environment
        or if the decoding/decompression fails
        ImportError: If FastAPI dependencies are not installed
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI dependencies not installed. "
            "Install with: pip install mycelium-http-tools[fastapi]"
        )

    verifier = active_verifier()
    profile_values, signature_values = header_values(
        request, profile_header, signature_header
    )
    if verifier is not None:
        return verified_profile(profile_values, signature_values, verifier)

    note_unverified_signature(signature_values)

    environment = os.getenv("ENVIRONMENT", "development")

    if environment != "development":
        if profile_header is None:
            raise HTTPException(
                status_code=403,
                detail=f"Required header '{DEFAULT_PROFILE_KEY}' missing in production environment.",
            )

        try:
            # Decode and decompress the profile from Base64/ZSTD
            return decode_and_decompress_profile_from_base64(profile_header)
        except ProfileDecodingError as e:
            logger.warning(
                f"Unable to decode and decompress profile: {e.message}"
            )
            raise HTTPException(
                status_code=401,
                detail="Unable to check user identity. Please contact administrators",
            )
        except Exception as e:
            logger.warning(f"Unable to check user identity due: {e}")
            raise HTTPException(
                status_code=401,
                detail="Unable to check user identity. Please contact administrators",
            )

    # In development mode, try to parse if header exists, otherwise return None
    if profile_header is not None:
        try:
            return decode_and_decompress_profile_from_base64(profile_header)
        except Exception as e:
            # In development, we're more lenient with errors
            logger.debug(f"Failed to decode profile in development mode: {e}")
            return None

    return None


def get_profile_from_header_required(
    profile_header: Annotated[str, Header(alias="x-mycelium-profile")],
    signature_header: Annotated[
        str | None, Header(alias=DEFAULT_PROFILE_SIGNATURE_KEY)
    ] = None,
    request: Request = None,
) -> Profile:
    """FastAPI dependency to extract profile from x-mycelium-profile header (required).

    This function requires the header to be present and will raise an error if missing.
    Use this when the profile is always required for the endpoint. The header should
    contain a Base64-encoded, ZSTD-compressed profile.

    Args:
        profile_header: The Base64-encoded, ZSTD-compressed profile string

    Returns:
        Profile object if successfully parsed

    Raises:
        HTTPException: If header is missing or decoding/decompression fails
        ImportError: If FastAPI dependencies are not installed
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI dependencies not installed. "
            "Install with: pip install mycelium-http-tools[fastapi]"
        )

    verifier = active_verifier()
    profile_values, signature_values = header_values(
        request, profile_header, signature_header
    )
    if verifier is not None:
        return verified_profile(profile_values, signature_values, verifier)

    note_unverified_signature(signature_values)

    try:
        # Decode and decompress the profile from Base64/ZSTD
        return decode_and_decompress_profile_from_base64(profile_header)
    except ProfileDecodingError as e:
        logger.warning(f"Unable to decode and decompress profile: {e.message}")
        raise HTTPException(
            status_code=401,
            detail="Unable to check user identity. Please contact administrators",
        )
    except Exception as e:
        logger.warning(f"Unable to check user identity due: {e}")
        raise HTTPException(
            status_code=401,
            detail="Unable to check user identity. Please contact administrators",
        )
