"""Gateway profile JWKS: shared contract and verifier behavior.

``mock/profile-signature/jwks-vectors.json`` is produced by the gateway from
its real publisher. This suite must accept or refuse every document exactly
as the gateway's Rust verifier does, derive the same cache lifetimes, and
show the key cache behaves like the Rust one: rotation without restart,
bounded refetch, single-flight, last valid set kept, bounded HTTP.
"""

import hashlib
import http.server
import json
import threading
import time
from pathlib import Path

import pytest

# The JWKS keys are Ed25519: this suite needs the `signature` extra.
pytest.importorskip("cryptography")
pytest.importorskip("jwt")

from myc_http_tools.exceptions import (  # noqa: E402
    ProfileJwksFetchError,
    ProfileSignatureConfigurationError,
    ProfileSignatureError,
)
from myc_http_tools.functions import (  # noqa: E402
    compress_and_encode_profile_to_base64,
)
from myc_http_tools.models.profile import Profile  # noqa: E402
from myc_http_tools.profile_jwks import (  # noqa: E402
    FetchedProfileJwks,
    JwksProfileSignatureVerifier,
    ProfileJwksUrl,
    ProfileKeyStore,
    fetch_profile_jwks,
    read_jwks_cache_max_age,
    read_signature_key_version,
    trusted_profile_keys_from_jwks,
)

MOCK = Path(__file__).parent / "mock" / "profile-signature"
FIXTURE = MOCK / "jwks-vectors.json"
GATEWAY_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "mycelium-api-gateway"
    / "lib"
    / "http_tools"
    / "test"
    / "mock"
    / "profile-signature"
    / "jwks-vectors.json"
)

CONTRACT = json.loads(FIXTURE.read_text(encoding="utf-8"))
VECTORS = CONTRACT["vectors"]

# TEST ONLY: RFC 8032 section 7.1 test vectors 1 and 2 (seeds)
SEEDS = {
    "1": "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
    "2": "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
}


# ? ---------------------------------------------------------------------------
# ? Contract vectors (Rust -> Python)
# ? ---------------------------------------------------------------------------


def outcome(document: str):
    try:
        keys = trusted_profile_keys_from_jwks(document.encode("utf-8"))
    except ProfileSignatureConfigurationError:
        return "invalid_jwks", []

    return "valid", sorted(keys)


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_jwks_vector(vector):
    assert outcome(vector["document"]) == (
        vector["expected"],
        vector["expectedKids"],
    )


@pytest.mark.parametrize(
    "case",
    CONTRACT["cacheControl"],
    ids=[str(case["cacheControl"]) for case in CONTRACT["cacheControl"]],
)
def test_cache_control_vector(case):
    assert (
        read_jwks_cache_max_age(case["cacheControl"])
        == case["expectedSeconds"]
    )


def test_published_document_parses_with_both_keys():
    assert outcome(CONTRACT["published"]) == ("valid", ["1", "2"])


def test_contract_constants_match_the_sdk():
    from myc_http_tools import settings

    contract = CONTRACT["contract"]
    assert contract["path"] == settings.PROFILE_JWKS_PATH
    assert contract["urlVariable"] == settings.PROFILE_JWKS_URL_ENV
    assert (
        contract["insecureHttpVariable"]
        == settings.PROFILE_JWKS_ALLOW_INSECURE_HTTP_ENV
    )
    assert contract["maxBytes"] == settings.PROFILE_JWKS_MAX_BYTES
    assert (
        contract["refetchCooldownSeconds"]
        == settings.PROFILE_JWKS_REFETCH_COOLDOWN_SECONDS
    )
    assert (
        contract["fetchTimeoutSeconds"]
        == settings.PROFILE_JWKS_FETCH_TIMEOUT_SECONDS
    )
    assert (
        contract["emptyRetrySeconds"]
        == settings.PROFILE_JWKS_EMPTY_RETRY_SECONDS
    )


@pytest.mark.skipif(
    not GATEWAY_FIXTURE.exists(), reason="gateway checkout not available"
)
def test_fixture_copy_matches_gateway_output():
    def digest(path: Path) -> str:
        normalized = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(normalized).hexdigest()

    assert digest(FIXTURE) == digest(GATEWAY_FIXTURE)


def test_reads_canonical_kid_only():
    import base64

    def token(header: str) -> str:
        encoded = base64.urlsafe_b64encode(header.encode()).rstrip(b"=")
        return f"{encoded.decode()}.e30.sig"

    assert read_signature_key_version(token('{"kid":"7"}')) == "7"
    assert read_signature_key_version(token('{"kid":"07"}')) is None
    assert read_signature_key_version(token('{"kid":7}')) is None
    assert read_signature_key_version(token("{}")) is None
    assert read_signature_key_version("%%%.x.y") is None


# ? ---------------------------------------------------------------------------
# ? A fake gateway whose published key set can change
# ? ---------------------------------------------------------------------------


def private_key(version: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(SEEDS[version]))


def jwks(versions) -> bytes:
    import base64

    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    keys = []
    for version in versions:
        raw = (
            private_key(version)
            .public_key()
            .public_bytes(Encoding.Raw, PublicFormat.Raw)
        )
        x = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        keys.append({"kty": "OKP", "crv": "Ed25519", "x": x, "kid": version})

    return json.dumps({"keys": keys}).encode()


class FakeGateway:
    def __init__(self, versions, max_age_seconds=600, delay=0.0):
        self.published = list(versions)
        self.max_age_seconds = max_age_seconds
        self.delay = delay
        self.fetches = 0
        self._lock = threading.Lock()

    def publish(self, versions):
        """``None`` makes every fetch fail (gateway down)."""
        self.published = None if versions is None else list(versions)

    def __call__(self, _url):
        with self._lock:
            self.fetches += 1
        time.sleep(self.delay)
        if self.published is None:
            raise ProfileJwksFetchError("gateway down")

        return FetchedProfileJwks(
            keys=trusted_profile_keys_from_jwks(jwks(self.published)),
            max_age_seconds=self.max_age_seconds,
        )


URL = ProfileJwksUrl.parse("https://gateway.test/jwks.json", False)


def verifier(gateway, cooldown_seconds):
    return JwksProfileSignatureVerifier(
        ProfileKeyStore(URL, gateway, cooldown_seconds), 60, "svc"
    )


def signed_by(version: str):
    import jwt

    from myc_http_tools.functions import profile_header_hash

    profile = Profile.model_validate(
        {
            "owners": [],
            "accId": "11111111-1111-4111-8111-111111111111",
            "isSubscription": False,
            "isManager": False,
            "isStaff": True,
            "ownerIsActive": True,
            "accountIsActive": True,
            "accountWasApproved": True,
            "accountWasArchived": False,
            "accountWasDeleted": False,
        }
    )
    header = compress_and_encode_profile_to_base64(profile)
    claims = {
        "iat": int(time.time()),
        "ph": profile_header_hash(header),
        "aud": "svc",
    }
    signature = jwt.encode(
        claims,
        private_key(version),
        algorithm="EdDSA",
        headers={"kid": version},
    )
    return header, signature


def verify(target, version):
    header, signature = signed_by(version)
    return target.verify_and_decode(header, signature)


# ? ---------------------------------------------------------------------------
# ? Key cache behavior
# ? ---------------------------------------------------------------------------


def test_rotation_is_picked_up_without_touching_the_downstream():
    gateway = FakeGateway(["1"])
    target = verifier(gateway, 0)
    target.prefetch()
    assert verify(target, "1").is_staff

    gateway.publish(["1", "2"])

    assert verify(target, "2").is_staff
    assert gateway.fetches == 2


def test_unknown_kid_refetches_at_most_once_per_cooldown():
    gateway = FakeGateway(["1"])
    target = verifier(gateway, 30)
    target.prefetch()

    for _ in range(2):
        with pytest.raises(ProfileSignatureError) as rejected:
            verify(target, "2")
        assert rejected.value.reason == "unknown_key"

    assert gateway.fetches == 1, "cooldown since the prefetch"


def test_concurrent_unknown_kids_share_one_fetch():
    gateway = FakeGateway(["1"], delay=0.05)
    target = verifier(gateway, 0)
    target.prefetch()
    gateway.publish(["1", "2"])
    results = []

    def run():
        results.append(verify(target, "2").is_staff)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results == [True] * 8
    assert gateway.fetches == 2


def test_a_failed_refresh_keeps_the_last_valid_set(caplog):
    gateway = FakeGateway(["1"], max_age_seconds=0)
    target = verifier(gateway, 0)
    target.prefetch()

    gateway.publish(None)

    assert verify(target, "1").is_staff
    assert gateway.fetches >= 2, "the stale set was refreshed"
    assert "keeping the last valid profile JWKS" in caplog.text


def test_prefetch_fails_when_the_gateway_is_unreachable():
    gateway = FakeGateway(["1"])
    gateway.publish(None)

    with pytest.raises(ProfileJwksFetchError):
        verifier(gateway, 0).prefetch()


def test_lazy_verifier_fetches_on_first_use():
    gateway = FakeGateway(["1"])
    target = verifier(gateway, 30)

    assert verify(target, "1").is_staff
    assert gateway.fetches == 1


def test_a_service_started_before_the_gateway_recovers_within_seconds():
    gateway = FakeGateway(["1"])
    now = [1000.0]
    store = ProfileKeyStore(URL, gateway, 30, clock=lambda: now[0])
    target = JwksProfileSignatureVerifier(store, 60, "svc")
    gateway.publish(None)
    with pytest.raises(ProfileSignatureError):
        verify(target, "1")

    gateway.publish(["1"])
    with pytest.raises(ProfileSignatureError):
        verify(target, "1")
    assert gateway.fetches == 1, "retry is bounded"

    now[0] += 5.1
    assert verify(target, "1").is_staff
    assert gateway.fetches == 2


def test_after_the_first_set_the_full_cooldown_applies():
    gateway = FakeGateway(["1"])
    now = [1000.0]
    store = ProfileKeyStore(URL, gateway, 30, clock=lambda: now[0])
    target = JwksProfileSignatureVerifier(store, 60, "svc")
    target.prefetch()

    now[0] += 5.1
    with pytest.raises(ProfileSignatureError):
        verify(target, "2")
    assert gateway.fetches == 1


def test_non_canonical_kid_never_triggers_a_fetch():
    import base64

    gateway = FakeGateway(["1"])
    target = verifier(gateway, 0)
    target.prefetch()
    header, signature = signed_by("1")
    protected = base64.urlsafe_b64encode(b'{"alg":"EdDSA","kid":"01"}').rstrip(
        b"="
    )
    forged = ".".join([protected.decode(), *signature.split(".")[1:]])

    with pytest.raises(ProfileSignatureError) as rejected:
        target.verify_and_decode(header, forged)

    assert rejected.value.reason == "unknown_key"
    assert gateway.fetches == 1


# ? ---------------------------------------------------------------------------
# ? Real HTTP fetch
# ? ---------------------------------------------------------------------------


class _Gateway(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        routes = {
            "/jwks.json": (
                200,
                {"Cache-Control": "public, max-age=600"},
                jwks(["1", "2"]),
            ),
            "/huge.json": (200, {}, b" " * (70 * 1024)),
            "/redirect.json": (302, {"Location": "/jwks.json"}, b""),
            "/missing.json": (404, {}, b""),
        }
        if self.path == "/slow.json":
            self._drip(jwks(["1", "2"]))
            return

        status, headers, body = routes[self.path]
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _drip(self, body: bytes) -> None:
        """Valid headers, then one body byte every 0.2 s (slow server)."""
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            for index in range(len(body)):
                self.wfile.write(body[index : index + 1])
                self.wfile.flush()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, *_args):
        return


@pytest.fixture
def local_gateway():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Gateway)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def local(base: str, path: str) -> ProfileJwksUrl:
    return ProfileJwksUrl.parse(f"{base}{path}", True)


def test_fetches_the_set_and_its_cache_lifetime_over_http(local_gateway):
    fetched = fetch_profile_jwks(local(local_gateway, "/jwks.json"))

    assert sorted(fetched.keys) == ["1", "2"]
    assert fetched.max_age_seconds == 600


@pytest.mark.parametrize(
    "path", ["/missing.json", "/huge.json", "/redirect.json"]
)
def test_refuses_errors_oversized_bodies_and_redirects(local_gateway, path):
    with pytest.raises(ProfileJwksFetchError):
        fetch_profile_jwks(local(local_gateway, path))


def test_a_slow_server_cannot_hold_the_fetch_past_the_deadline(
    local_gateway,
):
    """Each byte arrives well within the socket timeout; the total does not."""
    started = time.monotonic()

    with pytest.raises(ProfileJwksFetchError, match="exceeded"):
        fetch_profile_jwks(
            local(local_gateway, "/slow.json"), timeout_seconds=1.0
        )

    assert time.monotonic() - started < 2.0
