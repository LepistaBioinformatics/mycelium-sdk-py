import base64

from myc_http_tools.models.profile import Profile

try:
    import zstandard as zstd

    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False


def compress_and_encode_profile_to_base64(profile: Profile) -> str:
    """Encode a Profile into the gateway header form.

    Mirrors the gateway's compress_and_encode_profile_to_base64:
    JSON (camelCase) -> ZSTD (level 3) -> Base64 STANDARD. The output decodes
    with decode_and_decompress_profile_from_base64, the Go SDK, and the gateway.

    Requires the ``zstandard`` extra (install ``mycelium-http-tools[fastapi]``).
    """
    if not ZSTD_AVAILABLE:
        raise RuntimeError(
            "zstandard is required for profile encoding; install "
            "mycelium-http-tools[fastapi]"
        )

    json_bytes = profile.model_dump_json(
        by_alias=True, exclude_none=True
    ).encode("utf-8")

    compressed = zstd.ZstdCompressor(level=3).compress(json_bytes)

    return base64.standard_b64encode(compressed).decode("utf-8")
