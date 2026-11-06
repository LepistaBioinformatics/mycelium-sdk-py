"""Downstream profile signature: configuration and contract vectors.

The vectors in ``mock/profile-signature/vectors.json`` are produced by the
gateway's real encoder and signer (Rust). This suite must reach the same
decision and ``reason`` for every vector.
"""

import base64
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
from myc_http_tools.profile_jwks import (
    FetchedProfileJwks,
    trusted_profile_keys_from_jwks,
)
from myc_http_tools.profile_signature_config import (
    configure_profile_signature,
    get_profile_signature_verifier,
    load_profile_signature_verifier_from_env,
    reset_profile_signature_configuration,
)
from myc_http_tools.profile_signature_verifier import (
    ProfileSignatureVerifier,
    is_canonical_key_version,
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

JWKS_URL = "https://gateway.test/.well-known/mycelium-profile-jwks.json"


def jwks_document(versions) -> bytes:
    """JWKS of corpus SPKI PEMs (an Ed25519 SPKI ends with the raw key)."""
    keys = []
    for version in versions:
        body = "".join(
            line
            for line in PUBLIC_KEYS[version].splitlines()
            if not line.startswith("-----")
        )
        raw = base64.standard_b64decode(body)[-32:]
        x = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        keys.append({"kty": "OKP", "crv": "Ed25519", "x": x, "kid": version})

    return json.dumps({"keys": keys}).encode("utf-8")


def fetcher_for(versions):
    def fetch(_url):
        return FetchedProfileJwks(
            keys=trusted_profile_keys_from_jwks(jwks_document(versions)),
            max_age_seconds=600,
        )

    return fetch


def env_for(**extra):
    env = {
        "MYCELIUM_JWKS_URL": JWKS_URL,
        "MYC_PROFILE_SIGNATURE_AUDIENCE": "billing-api",
    }
    env.update(extra)
    return env


@pytest.mark.parametrize("raw", ["9007199254740992", "9" * 5000])
def test_tolerance_overflow_matches_javascript_configuration_error(raw):
    with pytest.raises(ProfileSignatureConfigurationError):
        load_profile_signature_verifier_from_env(
            env_for(MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS=raw)
        )


def test_tolerance_accepts_maximum_safe_integer():
    verifier = load_profile_signature_verifier_from_env(
        env_for(MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS="9007199254740991")
    )
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
    """One verification pass with the vector's keys read from a JWKS."""
    return ProfileSignatureVerifier(
        public_keys=trusted_profile_keys_from_jwks(
            jwks_document(vector["trustedKeyVersions"])
        ),
        tolerance_seconds=vector["toleranceSeconds"],
        expected_audience=vector["expectedAudience"],
    )


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


def test_no_jwks_url_means_disabled():
    assert load_profile_signature_verifier_from_env({}) is None
    assert (
        load_profile_signature_verifier_from_env(
            {
                "MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "30",
                "MYC_PROFILE_SIGNATURE_AUDIENCE": "billing-api",
            }
        )
        is None
    )


def test_reads_tolerance_and_audience():
    verifier = load_profile_signature_verifier_from_env(
        env_for(MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS="30")
    )

    assert verifier.tolerance_seconds == 30
    assert verifier.expected_audience == "billing-api"
    assert verifier.store.url.value == JWKS_URL


def test_audience_is_mandatory_when_enabled():
    with pytest.raises(ProfileSignatureConfigurationError) as error:
        load_profile_signature_verifier_from_env(
            {"MYCELIUM_JWKS_URL": JWKS_URL}
        )

    assert "MYC_PROFILE_SIGNATURE_AUDIENCE" in error.value.message


HTTP_URL = "http://gateway.test/jwks.json"


@pytest.mark.parametrize(
    ("switch", "accepted"),
    [(None, False), ("false", False), ("true", True), (" true ", True),
     ("yes", False)],
)
def test_plain_http_needs_the_development_switch(switch, accepted):
    env = env_for(MYCELIUM_JWKS_URL=HTTP_URL)
    if switch is not None:
        env["MYCELIUM_JWKS_ALLOW_INSECURE_HTTP"] = switch

    if accepted:
        assert load_profile_signature_verifier_from_env(env) is not None
        return

    with pytest.raises(ProfileSignatureConfigurationError):
        load_profile_signature_verifier_from_env(env)


@pytest.mark.parametrize(
    "env",
    [
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "0"},
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "-5"},
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "sixty"},
        {"MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS": "1.5"},
        {"MYC_PROFILE_SIGNATURE_AUDIENCE": "  "},
        {"MYCELIUM_JWKS_ALLOW_INSECURE_HTTP": "maybe"},
        env_for(MYCELIUM_JWKS_URL=""),
        env_for(MYCELIUM_JWKS_URL="/.well-known/mycelium-profile-jwks.json"),
        env_for(MYCELIUM_JWKS_URL="ftp://gateway/jwks.json"),
        env_for(MYCELIUM_JWKS_URL="file:///etc/jwks.json"),
        env_for(MYCELIUM_JWKS_URL="https://user:secret@gateway/jwks.json"),
    ],
)
def test_invalid_configuration_never_disables(env):
    with pytest.raises(ProfileSignatureConfigurationError) as error:
        load_profile_signature_verifier_from_env(env)

    assert "secret" not in error.value.message


def test_missing_optional_dependencies_is_a_configuration_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "jwt", None)

    with pytest.raises(ProfileSignatureConfigurationError) as error:
        load_profile_signature_verifier_from_env(env_for())

    assert "mycelium-http-tools[signature]" in error.value.message


# ? ---------------------------------------------------------------------------
# ? Process state: lazy loading, never at import time
# ? ---------------------------------------------------------------------------


@pytest.fixture
def clean_state(monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith(("MYC_PROFILE_", "MYCELIUM_JWKS_")):
            monkeypatch.delenv(name)
    reset_profile_signature_configuration()
    yield
    reset_profile_signature_configuration()


def test_env_set_after_import_is_honored(clean_state, monkeypatch):
    import myc_http_tools.fastapi  # noqa: F401  (import happens first)

    for name, value in env_for().items():
        monkeypatch.setenv(name, value)

    verifier = get_profile_signature_verifier()
    assert verifier is not None
    assert verifier.expected_audience == "billing-api"


def test_lazy_state_is_cached(clean_state, monkeypatch):
    assert get_profile_signature_verifier() is None

    for name, value in env_for().items():
        monkeypatch.setenv(name, value)
    assert get_profile_signature_verifier() is None


def test_lazy_configuration_error_is_cached_and_raised(
    clean_state, monkeypatch
):
    monkeypatch.setenv("MYCELIUM_JWKS_URL", "ftp://broken")

    for _ in range(2):
        with pytest.raises(ProfileSignatureConfigurationError):
            get_profile_signature_verifier()


def test_lazy_loading_never_touches_the_network(clean_state, monkeypatch):
    import socket

    def forbidden(*_args, **_kwargs):
        pytest.fail("lazy configuration attempted network IO")

    monkeypatch.setattr(socket, "socket", forbidden)
    for name, value in env_for().items():
        monkeypatch.setenv(name, value)

    assert get_profile_signature_verifier() is not None


def test_configure_raises_at_startup(clean_state):
    with pytest.raises(ProfileSignatureConfigurationError):
        configure_profile_signature({"MYCELIUM_JWKS_URL": "ftp://broken"})

    verifier = configure_profile_signature(
        env_for(), fetcher=fetcher_for(["2"]), prefetch=True
    )
    assert get_profile_signature_verifier() is verifier
    assert list(verifier.store.current()[0]) == ["2"]


def test_configure_does_not_need_the_gateway_by_default(clean_state):
    def gateway_down(_url):
        raise AssertionError("must not fetch at startup")

    verifier = configure_profile_signature(env_for(), fetcher=gateway_down)

    assert verifier is not None
    assert dict(verifier.store.current()[0]) == {}
