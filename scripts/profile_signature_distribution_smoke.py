"""Run from outside the source tree against an installed wheel (signature extra)."""
import json
import sys
from pathlib import Path

import myc_http_tools
from myc_http_tools.exceptions import ProfileSignatureError
from myc_http_tools.functions import verify_and_decode_profile
from myc_http_tools.profile_signature_config import load_profile_signature_verifier_from_env

fixture = json.loads(Path(sys.argv[1]).read_text())
assert "site-packages" in str(Path(myc_http_tools.__file__).resolve()), "must exercise installed wheel"
for vector in fixture["vectors"]:
    env = {f"MYC_PROFILE_PUBLIC_KEY_{v}": fixture["publicKeys"][v] for v in vector["trustedKeyVersions"]}
    env["MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS"] = str(vector["toleranceSeconds"])
    if vector["expectedAudience"] is not None:
        env["MYC_PROFILE_SIGNATURE_AUDIENCE"] = vector["expectedAudience"]
    verifier = load_profile_signature_verifier_from_env(env)
    assert verifier is not None
    outcome = "valid"
    try:
        profile = verify_and_decode_profile(vector["profileHeader"], vector["signature"], verifier, now_seconds=vector["nowSeconds"])
        assert str(profile.acc_id) == fixture["expectedValidProfile"]["accId"]
    except ProfileSignatureError as error:
        outcome = error.reason
    assert outcome == vector["expected"], vector["name"]
print(f"PASS Python {sys.version.split()[0]} installed wheel: {len(fixture['vectors'])} Rust vectors")
