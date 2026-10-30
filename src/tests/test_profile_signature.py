"""Downstream profile signature: configuration and contract vectors.

The vectors in ``mock/profile-signature/vectors.json`` are produced by the
gateway's real encoder and signer (Rust). This suite must reach the same
decision and ``reason`` for every vector.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from myc_http_tools.exceptions import (
    ProfileSignatureConfigurationError,
    ProfileSignatureError,
)
from myc_http_tools.functions import (
    profile_header_hash,
    verify_and_decode_profile,
    verify_profile_signature,
)
from myc_http_tools.profile_signature_config import (
    ProfileSignatureVerifier,
    configure_profile_signature,
    get_profile_signature_verifier,
    is_canonical_key_version,
    load_profile_signature_verifier_from_env,
    reset_profile_signature_configuration,
)

FIXTURE = Path(__file__).parent / "mock" / "profile-signature" / "vectors.json"
GATEWAY_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "mycelium-api-gateway"
    / "lib"
    / "http_tools"
    / "test"
    / "mock"
    / "profile-signature"
    / "vectors.json"
)

CONTRACT = json.loads(FIXTURE.read_text(encoding="utf-8"))
PUBLIC_KEYS = CONTRACT["publicKeys"]
VECTORS = CONTRACT["vectors"]

TEST_PRIVATE_PEM_V1 = """-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIJ1hsZ3v/VpguoRK9JLsLMREScVpezJpGXA7rAMcrn9g
-----END PRIVATE KEY-----
"""


def env_for(versions, **extra):
    env = {f"MYC_PROFILE_PUBLIC_KEY_{v}": PUBLIC_KEYS[v] for v in versions}
    env.update(extra)
    return env


@pytest.mark.parametrize("raw", ["9007199254740992", "9" * 5000])
def test_tolerance_overflow_matches_javascript_configuration_error(raw):
    with pytest.raises(ProfileSignatureConfigurationError):
        load_profile_signature_verifier_from_env(env_for(["1"], MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS=raw))


def test_tolerance_accepts_maximum_safe_integer():
    verifier = load_profile_signature_verifier_from_env(env_for(["1"], MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS="9007199254740991"))
    assert verifier.tolerance_seconds == 9_007_199_254_740_991


def test_oversized_key_version_is_not_parsed_as_an_unbounded_integer():
    assert not is_canonical_key_version("9" * 5000)


def test_prepared_verifier_reuses_key_without_pem_file_or_network_io(monkeypatch):
    import builtins
    import socket
    import cryptography.hazmat.primitives.serialization as serialization

    vector = VECTORS[0]
    verifier = verifier_for(vector)
    verify_and_decode_profile(vector["profileHeader"], vector["signature"], verifier,
                              now_seconds=vector["nowSeconds"])

    def forbidden(*_args, **_kwargs):
        pytest.fail("prepared verification attempted configuration or IO")

    monkeypatch.setattr(serialization, "load_pem_public_key", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    for _ in range(3):
        verify_and_decode_profile(vector["profileHeader"], vector["signature"], verifier,
                                  now_seconds=vector["nowSeconds"])


def verifier_for(vector) -> ProfileSignatureVerifier:
    extra = {
        "MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": str(
            vector["toleranceSeconds"]
        )
    }
    if vector["expectedAudience"] is not None:
        extra["MYC_PROFILE_SIGNATURE_AUDIENCE"] = vector["expectedAudience"]

    verifier = load_profile_signature_verifier_from_env(
        env_for(vector["trustedKeyVersions"], **extra)
    )
    assert verifier is not None
    return verifier


# ? ---------------------------------------------------------------------------
# ? Contract vectors (Rust -> Python)
# ? ---------------------------------------------------------------------------


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_contract_vector(vector):
    verifier = verifier_for(vector)

    if vector["expected"] == "valid":
        profile = verify_and_decode_profile(
            vector["profileHeader"],
            vector["signature"],
            verifier,
            now_seconds=vector["nowSeconds"],
        )
        expected = CONTRACT["expectedValidProfile"]
        assert str(profile.acc_id) == expected["accId"]
        assert profile.is_staff is expected["isStaff"]
        return

    with pytest.raises(ProfileSignatureError) as rejected:
        verify_and_decode_profile(
            vector["profileHeader"],
            vector["signature"],
            verifier,
            now_seconds=vector["nowSeconds"],
        )

    assert rejected.value.reason == vector["expected"]
    assert rejected.value.code == "MYC_PROFILE_SIGNATURE_INVALID"


def test_contract_covers_every_reason():
    reasons = {vector["expected"] for vector in VECTORS}

    assert reasons >= {
        "valid",
        "missing_signature",
        "malformed_signature",
        "unsupported_algorithm",
        "unknown_key",
        "invalid_signature",
        "invalid_claims",
        "timestamp_out_of_tolerance",
        "profile_hash_mismatch",
        "audience_mismatch",
        "invalid_profile",
    }


@pytest.mark.skipif(
    not GATEWAY_FIXTURE.exists(), reason="gateway checkout not available"
)
def test_fixture_copy_matches_gateway_output():
    def digest(path: Path) -> str:
        normalized = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(normalized).hexdigest()

    assert digest(FIXTURE) == digest(GATEWAY_FIXTURE)


def test_decodes_real_gateway_profile_without_content_size():
    """Regression: gateway ZSTD frames do not declare the content size."""
    from myc_http_tools.functions import (
        decode_and_decompress_profile_from_base64,
    )

    import base64

    import zstandard

    header = VECTORS[0]["profileHeader"]
    frame = base64.standard_b64decode(header)

    assert (
        zstandard.get_frame_parameters(frame).content_size
        == zstandard.CONTENTSIZE_UNKNOWN
    )
    profile = decode_and_decompress_profile_from_base64(header)
    assert str(profile.acc_id) == CONTRACT["expectedValidProfile"]["accId"]


def test_profile_header_hash_matches_rfc_vector():
    assert (
        profile_header_hash("abc")
        == "ungWv48Bz-pBQUDeXa4iI7ADYaOWF3qctBD_YfIAFa0"
    )


def test_missing_profile_is_rejected_before_parsing():
    verifier = verifier_for(VECTORS[0])

    with pytest.raises(ProfileSignatureError) as rejected:
        verify_profile_signature("", VECTORS[0]["signature"], verifier)

    assert rejected.value.reason == "missing_profile"


@pytest.mark.parametrize("bad_clock", [-1, 2**53, True, 1.5])
def test_invalid_verifier_clock_fails_closed(bad_clock):
    vector = VECTORS[0]

    with pytest.raises(ValueError):
        verify_profile_signature(
            vector["profileHeader"],
            vector["signature"],
            verifier_for(vector),
            now_seconds=bad_clock,
        )


# ? ---------------------------------------------------------------------------
# ? Configuration
# ? ---------------------------------------------------------------------------


def test_no_public_key_means_disabled():
    assert load_profile_signature_verifier_from_env({}) is None
    assert (
        load_profile_signature_verifier_from_env(
            {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "30"}
        )
        is None
    )


def test_rotation_keyset_is_immutable():
    verifier = load_profile_signature_verifier_from_env(env_for(["1", "2"]))

    assert sorted(verifier.public_keys) == ["1", "2"]
    assert verifier.tolerance_seconds == 60
    assert verifier.expected_audience is None
    with pytest.raises(TypeError):
        verifier.public_keys["3"] = verifier.public_keys["1"]  # type: ignore[index]


@pytest.mark.parametrize(
    "env",
    [
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "0"},
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "-5"},
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "sixty"},
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "1.5"},
        {"MYC_PROFILE_SIGNATURE_AUDIENCE": "  "},
        {"MYC_PROFILE_PUBLIC_KEY_": "x"},
        {"MYC_PROFILE_PUBLIC_KEY_0": "x"},
        {"MYC_PROFILE_PUBLIC_KEY_01": "x"},
        {"MYC_PROFILE_PUBLIC_KEY_4294967296": "x"},
        {"MYC_PROFILE_PUBLIC_KEY_V1": "x"},
        {"MYC_PROFILE_PUBLIC_KEY_1": ""},
        {"MYC_PROFILE_PUBLIC_KEY_1": "not a pem"},
        {"MYC_PROFILE_PUBLIC_KEY_1": TEST_PRIVATE_PEM_V1},
    ],
)
def test_invalid_configuration_never_disables(env):
    with pytest.raises(ProfileSignatureConfigurationError) as error:
        load_profile_signature_verifier_from_env(env)

    assert "MIIB" not in error.value.message
    assert "BEGIN" not in error.value.message


def test_rejects_non_ed25519_public_key():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    pem = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )

    with pytest.raises(ProfileSignatureConfigurationError):
        load_profile_signature_verifier_from_env(
            {"MYC_PROFILE_PUBLIC_KEY_1": pem}
        )


def test_missing_optional_dependencies_is_a_configuration_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "jwt", None)

    with pytest.raises(ProfileSignatureConfigurationError) as error:
        load_profile_signature_verifier_from_env(env_for(["1"]))

    assert "mycelium-http-tools[signature]" in error.value.message


# ? ---------------------------------------------------------------------------
# ? Process state: lazy loading, never at import time
# ? ---------------------------------------------------------------------------


@pytest.fixture
def clean_state(monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith("MYC_PROFILE_"):
            monkeypatch.delenv(name)
    reset_profile_signature_configuration()
    yield
    reset_profile_signature_configuration()


def test_env_set_after_import_is_honored(clean_state, monkeypatch):
    import myc_http_tools.fastapi  # noqa: F401  (import happens first)

    monkeypatch.setenv("MYC_PROFILE_PUBLIC_KEY_1", PUBLIC_KEYS["1"])

    verifier = get_profile_signature_verifier()
    assert verifier is not None
    assert list(verifier.public_keys) == ["1"]


def test_lazy_state_is_cached(clean_state, monkeypatch):
    assert get_profile_signature_verifier() is None

    monkeypatch.setenv("MYC_PROFILE_PUBLIC_KEY_1", PUBLIC_KEYS["1"])
    assert get_profile_signature_verifier() is None


def test_lazy_configuration_error_is_cached_and_raised(clean_state, monkeypatch):
    monkeypatch.setenv("MYC_PROFILE_PUBLIC_KEY_1", "broken")

    for _ in range(2):
        with pytest.raises(ProfileSignatureConfigurationError):
            get_profile_signature_verifier()


def test_configure_raises_at_startup(clean_state):
    with pytest.raises(ProfileSignatureConfigurationError):
        configure_profile_signature({"MYC_PROFILE_PUBLIC_KEY_1": "broken"})

    verifier = configure_profile_signature(env_for(["2"]))
    assert get_profile_signature_verifier() is verifier
