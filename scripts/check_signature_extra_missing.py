"""CI smoke: run in an environment WITHOUT the `signature` extra.

Asserts that the package imports and decodes profiles without PyJWT /
cryptography, and that enabling verification (MYCELIUM_JWKS_URL) raises a
configuration error pointing to the extra (never "verification disabled").
"""

import importlib.util
import sys

from myc_http_tools import ProfileSignatureConfigurationError
from myc_http_tools.profile_signature_config import (
    load_profile_signature_verifier_from_env,
)

for module in ("jwt", "cryptography"):
    if importlib.util.find_spec(module) is not None:
        sys.exit(f"{module} is installed: this check needs a clean environment")

assert load_profile_signature_verifier_from_env({}) is None

try:
    load_profile_signature_verifier_from_env(
        {
            "MYCELIUM_JWKS_URL": "https://gateway.test/jwks.json",
            "MYC_PROFILE_SIGNATURE_AUDIENCE": "svc",
        }
    )
except ProfileSignatureConfigurationError as error:
    assert "mycelium-http-tools[signature]" in error.message, error.message
    print("ok: missing extra reported as a configuration error")
else:
    sys.exit("enabled verification without the extra did not raise")
