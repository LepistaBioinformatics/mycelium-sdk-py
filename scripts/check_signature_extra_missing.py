"""CI smoke: run in an environment WITHOUT the `signature` extra.

Asserts that the package imports and decodes profiles without PyJWT /
cryptography, and that configuring a public key raises a configuration error
pointing to the extra (never "verification disabled").
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
        {"MYC_PROFILE_PUBLIC_KEY_1": "-----BEGIN PUBLIC KEY-----"}
    )
except ProfileSignatureConfigurationError as error:
    assert "mycelium-http-tools[signature]" in error.message, error.message
    print("ok: missing extra reported as a configuration error")
else:
    sys.exit("configured key without the extra did not raise")
