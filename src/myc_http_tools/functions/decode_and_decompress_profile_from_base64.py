"""Decode and decompress profile from Base64.

This module provides a function to decode a Base64-encoded, ZSTD-compressed
profile string and return a Profile object.
"""

import base64
import json
import logging
from typing import Union

from myc_http_tools.exceptions import ProfileDecodingError
from myc_http_tools.models.profile import Profile

try:
    import zstandard as zstd

    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False
    zstd = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


def decode_and_decompress_profile_from_base64_robust(
    profile: Union[str, bytes],
    strict: bool = True,
) -> Profile:
    """Decode and decompress a profile from Base64.

    Reverses the gateway header encoding: Base64 STANDARD decode -> ZSTD
    decompress -> JSON deserialize.

    Args:
        profile: The Base64-encoded profile string or bytes.
        strict: When True (the default), a ZSTD decompression failure raises.
            When False, the Base64-decoded bytes are treated as
            already-uncompressed (dev mode where the gateway did not compress
            the profile). Mirrors the JS/Go SDK ``strict`` option.

    Returns:
        Profile: The decoded profile.

    Raises:
        ProfileDecodingError: On invalid Base64, failed decompression (strict),
            or failed deserialization.
    """
    if not profile:
        raise ProfileDecodingError("Profile input is empty")

    # Decode from Base64 first
    try:
        if isinstance(profile, str):
            profile_bytes = profile.encode("utf-8")
        else:
            profile_bytes = profile

        decoded_profile = base64.standard_b64decode(profile_bytes)
    except Exception as e:
        raise ProfileDecodingError(
            f"Failed to decode base64 profile: {e}"
        ) from e

    # ZSTD decompression (expected format)
    if ZSTD_AVAILABLE:
        try:
            decompressor = zstd.ZstdDecompressor()
            decompressed_profile = decompressor.decompress(decoded_profile)
            logger.debug("Successfully decompressed profile using ZSTD")
        except Exception as zstd_error:
            if strict:
                raise ProfileDecodingError(
                    f"Failed to decompress profile: {zstd_error}"
                ) from zstd_error
            # Non-strict: treat the Base64-decoded bytes as uncompressed.
            logger.info(
                f"ZSTD decompression failed ({zstd_error}), "
                "falling back to uncompressed bytes"
            )
            decompressed_profile = decoded_profile
    else:
        # ZSTD not available, use plain Base64
        logger.debug("ZSTD not available, using plain Base64 decoding")
        decompressed_profile = decoded_profile

    # Deserialize from JSON
    try:
        profile_string = decompressed_profile.decode("utf-8")
    except Exception as e:
        raise ProfileDecodingError(
            f"Failed to convert decompressed profile to string: {e}"
        ) from e

    try:
        profile_dict = json.loads(profile_string)
        return Profile.model_validate(profile_dict)
    except Exception as e:
        raise ProfileDecodingError(f"Failed to deserialize profile: {e}") from e
