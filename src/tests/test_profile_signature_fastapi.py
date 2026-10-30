"""Profile signature enforcement in the four FastAPI entry points.

The verifier clock is frozen at the instant the Rust vectors were issued, so
these tests exercise gateway-produced signatures end to end over HTTP.
"""

import json
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from myc_http_tools.fastapi import (
    get_profile_from_header,
    get_profile_from_header_required,
    get_profile_from_request,
    profile_middleware,
)
from myc_http_tools.profile_signature_config import (
    configure_profile_signature,
    reset_profile_signature_configuration,
)
from myc_http_tools.settings import (
    DEFAULT_PROFILE_KEY,
    DEFAULT_PROFILE_SIGNATURE_KEY,
)

CONTRACT = json.loads(
    (
        Path(__file__).parent / "mock" / "profile-signature" / "vectors.json"
    ).read_text(encoding="utf-8")
)
VECTORS = {vector["name"]: vector for vector in CONTRACT["vectors"]}
VALID = VECTORS["valid_v1"]
ACCOUNT = CONTRACT["expectedValidProfile"]["accId"]

ENTRY_POINTS = ["request", "middleware", "header", "header_required"]


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("entry_point", ENTRY_POINTS)
def test_unexpected_verification_error_is_generic_500_without_handler(
    enabled, monkeypatch, calls, entry_point, environment, caplog
):
    import sys
    module = sys.modules["myc_http_tools.fastapi.enforce_profile_signature"]

    def broken(*_args, **_kwargs):
        raise RuntimeError("PRIVATE-INTERNAL-MARKER")

    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setattr(module, "verify_and_decode_profile", broken)
    response = get(build_app(entry_point, calls), signed_headers())
    assert response.status_code == 500
    assert response.json() == {"detail": module.INTERNAL_DETAIL}
    assert calls["count"] == 0
    assert "PRIVATE-INTERNAL-MARKER" not in response.text + caplog.text


@pytest.fixture
def calls():
    return {"count": 0}


def build_app(entry_point: str, calls: dict) -> FastAPI:
    app = FastAPI()

    if entry_point == "middleware":
        app.add_middleware(BaseHTTPMiddleware, dispatch=profile_middleware)

        @app.get("/whoami")
        def whoami_state(request: Request):
            calls["count"] += 1
            profile = request.state.profile
            return {"accId": None if profile is None else str(profile.acc_id)}

        return app

    dependency = {
        "header": get_profile_from_header,
        "header_required": get_profile_from_header_required,
    }.get(entry_point)

    if dependency is None:

        @app.get("/whoami")
        def whoami_request(request: Request):
            profile = get_profile_from_request(request)
            calls["count"] += 1
            return {"accId": None if profile is None else str(profile.acc_id)}

        return app

    @app.get("/whoami")
    def whoami(profile=Depends(dependency)):
        calls["count"] += 1
        return {"accId": None if profile is None else str(profile.acc_id)}

    return app


@pytest.fixture
def frozen_clock(monkeypatch):
    import sys

    module = sys.modules["myc_http_tools.functions.verify_profile_signature"]
    monkeypatch.setattr(module.time, "time", lambda: float(VALID["nowSeconds"]))


@pytest.fixture
def enabled(frozen_clock):
    configure_profile_signature(
        {"MYC_PROFILE_PUBLIC_KEY_1": CONTRACT["publicKeys"]["1"]}
    )
    yield
    reset_profile_signature_configuration()


@pytest.fixture
def disabled():
    configure_profile_signature({})
    yield
    reset_profile_signature_configuration()


def signed_headers(vector=VALID):
    return [
        (DEFAULT_PROFILE_KEY, vector["profileHeader"]),
        (DEFAULT_PROFILE_SIGNATURE_KEY, vector["signature"]),
    ]


def get(app: FastAPI, headers):
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.get("/whoami", headers=headers)


# ? ---------------------------------------------------------------------------
# ? Enabled: fail closed in every environment
# ? ---------------------------------------------------------------------------


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("entry_point", ENTRY_POINTS)
def test_valid_gateway_signature_exposes_profile(
    enabled, monkeypatch, calls, entry_point, environment
):
    monkeypatch.setenv("ENVIRONMENT", environment)

    response = get(build_app(entry_point, calls), signed_headers())

    assert response.status_code == 200
    assert response.json() == {"accId": ACCOUNT}
    assert calls["count"] == 1


REJECTIONS = {
    "missing_signature": [(DEFAULT_PROFILE_KEY, VALID["profileHeader"])],
    "forged_profile": [
        (DEFAULT_PROFILE_KEY, VECTORS["profile_appended_byte"]["profileHeader"]),
        (DEFAULT_PROFILE_SIGNATURE_KEY, VALID["signature"]),
    ],
    "swapped_profile": signed_headers(VECTORS["profile_swapped"]),
    "unknown_key": signed_headers(VECTORS["unknown_key_version"]),
    "duplicate_signature": signed_headers()
    + [(DEFAULT_PROFILE_SIGNATURE_KEY, VALID["signature"])],
    "duplicate_profile": signed_headers()
    + [(DEFAULT_PROFILE_KEY, VALID["profileHeader"])],
    "alg_none": signed_headers(VECTORS["alg_none"]),
    "undecodable_profile": signed_headers(VECTORS["profile_not_decodable"]),
}


@pytest.mark.parametrize("environment", ["development", "production"])
@pytest.mark.parametrize("case", sorted(REJECTIONS))
@pytest.mark.parametrize("entry_point", ENTRY_POINTS)
def test_rejections_never_reach_the_handler(
    enabled, monkeypatch, calls, entry_point, case, environment
):
    monkeypatch.setenv("ENVIRONMENT", environment)

    response = get(build_app(entry_point, calls), REJECTIONS[case])

    assert response.status_code == 403
    assert response.json() == {"detail": "Unable to verify Mycelium profile"}
    assert calls["count"] == 0


@pytest.mark.parametrize("entry_point", ["request", "middleware", "header"])
def test_missing_profile_and_signature_is_rejected(
    enabled, monkeypatch, calls, entry_point
):
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = get(build_app(entry_point, calls), [])

    assert response.status_code == 403
    assert calls["count"] == 0


def test_required_dependency_keeps_422_for_missing_profile(enabled, calls):
    response = get(build_app("header_required", calls), [])

    assert response.status_code == 422
    assert calls["count"] == 0


@pytest.mark.parametrize("entry_point", ENTRY_POINTS)
def test_lazy_configuration_error_fails_closed_with_500(
    frozen_clock, monkeypatch, calls, entry_point
):
    reset_profile_signature_configuration()
    monkeypatch.setenv("MYC_PROFILE_PUBLIC_KEY_1", "broken")
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = get(build_app(entry_point, calls), signed_headers())

    reset_profile_signature_configuration()
    assert response.status_code == 500
    assert "broken" not in response.text
    assert calls["count"] == 0


def test_direct_call_of_header_dependency_verifies(enabled):
    profile = get_profile_from_header(
        VALID["profileHeader"], VALID["signature"]
    )
    assert str(profile.acc_id) == ACCOUNT

    with pytest.raises(Exception) as rejected:
        get_profile_from_header(VALID["profileHeader"])
    assert getattr(rejected.value, "status_code", None) == 403


# ? ---------------------------------------------------------------------------
# ? Disabled: legacy behavior preserved
# ? ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry_point", ENTRY_POINTS)
def test_disabled_ignores_signature_header(disabled, calls, entry_point):
    headers = [
        (DEFAULT_PROFILE_KEY, VALID["profileHeader"]),
        (DEFAULT_PROFILE_SIGNATURE_KEY, "not-even-a-jws"),
    ]

    response = get(build_app(entry_point, calls), headers)

    assert response.status_code == 200
    assert response.json() == {"accId": ACCOUNT}


@pytest.mark.parametrize("entry_point", ["request", "middleware", "header"])
def test_disabled_development_still_allows_missing_profile(
    disabled, monkeypatch, calls, entry_point
):
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = get(build_app(entry_point, calls), [])

    assert response.status_code == 200
    assert response.json() == {"accId": None}
