"""Run from outside the source tree against an installed wheel (signature extra).

Usage: profile_signature_distribution_smoke.py <path to vectors.json>
``jwks-vectors.json`` is read from the same directory.
"""
import base64
import json
import sys
from pathlib import Path

import myc_http_tools
from myc_http_tools.exceptions import (
    ProfileSignatureConfigurationError,
    ProfileSignatureError,
)
from myc_http_tools.functions import verify_and_decode_profile
from myc_http_tools.profile_jwks import (
    read_jwks_cache_max_age,
    trusted_profile_keys_from_jwks,
)
from myc_http_tools.profile_signature_verifier import ProfileSignatureVerifier

vectors_path = Path(sys.argv[1])
fixture = json.loads(vectors_path.read_text())
jwks_fixture = json.loads(
    (vectors_path.parent / "jwks-vectors.json").read_text()
)
assert "site-packages" in str(Path(myc_http_tools.__file__).resolve()), "must exercise installed wheel"


def jwks_for(versions):
    keys = []
    for version in versions:
        pem = fixture["publicKeys"][version]
        body = "".join(
            line for line in pem.splitlines() if not line.startswith("-----")
        )
        raw = base64.standard_b64decode(body)[-32:]
        x = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        keys.append({"kty": "OKP", "crv": "Ed25519", "x": x, "kid": version})
    return json.dumps({"keys": keys}).encode()


for vector in fixture["vectors"]:
    verifier = ProfileSignatureVerifier(
        public_keys=trusted_profile_keys_from_jwks(jwks_for(vector["trustedKeyVersions"])),
        tolerance_seconds=vector["toleranceSeconds"],
        expected_audience=vector["expectedAudience"],
    )
    outcome = "valid"
    try:
        profile = verify_and_decode_profile(vector["profileHeader"], vector["signature"], verifier, now_seconds=vector["nowSeconds"])
        assert str(profile.acc_id) == fixture["expectedValidProfile"]["accId"]
    except ProfileSignatureError as error:
        outcome = error.reason
    assert outcome == vector["expected"], vector["name"]

for vector in jwks_fixture["vectors"]:
    try:
        kids = sorted(trusted_profile_keys_from_jwks(vector["document"].encode()))
        outcome = "valid"
    except ProfileSignatureConfigurationError:
        kids, outcome = [], "invalid_jwks"
    assert (outcome, kids) == (vector["expected"], vector["expectedKids"]), vector["name"]

for case in jwks_fixture["cacheControl"]:
    assert read_jwks_cache_max_age(case["cacheControl"]) == case["expectedSeconds"]

print(
    f"PASS Python {sys.version.split()[0]} installed wheel: "
    f"{len(fixture['vectors'])} signature vectors, "
    f"{len(jwks_fixture['vectors'])} JWKS vectors"
)
