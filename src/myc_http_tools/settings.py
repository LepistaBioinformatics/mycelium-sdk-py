DEFAULT_PROFILE_KEY = "x-mycelium-profile"

DEFAULT_PROFILE_SIGNATURE_KEY = "x-mycelium-profile-signature"

# URL of the gateway profile JWKS. Its presence enables verification.
PROFILE_JWKS_URL_ENV = "MYCELIUM_JWKS_URL"

# Development-only switch that accepts an ``http://`` JWKS URL.
PROFILE_JWKS_ALLOW_INSECURE_HTTP_ENV = "MYCELIUM_JWKS_ALLOW_INSECURE_HTTP"

# Path where the gateway publishes the profile JWKS.
PROFILE_JWKS_PATH = "/.well-known/mycelium-profile-jwks.json"

PROFILE_JWKS_FETCH_TIMEOUT_SECONDS = 5

PROFILE_JWKS_MAX_BYTES = 64 * 1024

# Minimum interval between JWKS requests (unknown ``kid``, failed refresh).
PROFILE_JWKS_REFETCH_COOLDOWN_SECONDS = 30

# Shorter retry interval while no key set was ever downloaded (first use).
PROFILE_JWKS_EMPTY_RETRY_SECONDS = 5

PROFILE_JWKS_DEFAULT_MAX_AGE_SECONDS = 43_200

PROFILE_JWKS_MIN_MAX_AGE_SECONDS = 60

PROFILE_JWKS_MAX_MAX_AGE_SECONDS = 86_400

PROFILE_SIGNATURE_TOLERANCE_ENV = "MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS"

# Expected ``aud``, required whenever verification is enabled.
PROFILE_SIGNATURE_AUDIENCE_ENV = "MYC_PROFILE_SIGNATURE_AUDIENCE"

DEFAULT_PROFILE_SIGNATURE_TOLERANCE_SECONDS = 60

MAX_PROFILE_SIGNATURE_BYTES = 4096

MAX_SAFE_TIMESTAMP_SECONDS = 9_007_199_254_740_991

DEFAULT_EMAIL_KEY = "x-mycelium-email"

DEFAULT_SCOPE_KEY = "x-mycelium-scope"

DEFAULT_MYCELIUM_ROLE_KEY = "x-mycelium-role"

DEFAULT_REQUEST_ID_KEY = "x-mycelium-request-id"

DEFAULT_CONNECTION_STRING_KEY = "x-mycelium-connection-string"

DEFAULT_TENANT_ID_KEY = "x-mycelium-tenant-id"
