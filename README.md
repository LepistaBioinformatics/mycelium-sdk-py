# mycelium-sdk-py

Mycelium SDK for Python backends — decode the `x-mycelium-profile` header injected by the
Mycelium API Gateway and enforce tenant/account/role authorization with a fluent, typed API.
Published on PyPI as `mycelium-http-tools` (import as `myc_http_tools`).

Part of the Mycelium SDK family, alongside
[`mycelium-sdk-go`](https://github.com/LepistaBioinformatics/mycelium-sdk-go) (Go) and
[`mycelium-sdk-js`](https://github.com/LepistaBioinformatics/mycelium-sdk-js) (Node/TypeScript).
All three have full parity against the gateway's Rust `core::Profile` — the same method
surface (`permit_flags`/`deny_flags`, tenant-wide and admin helpers) and the same wire
contract (`perm` serialized as `"read"`/`"write"`).

## Requirements

- Python **>= 3.12**
- The `fastapi` extra pulls in `zstandard` (required to decode/encode compressed profiles)
  and `fastapi`

## Install

```bash
# Core only (framework-agnostic)
pip install mycelium-http-tools

# With the FastAPI adapter (+ zstandard)
pip install mycelium-http-tools[fastapi]

# With profile signature verification (PyJWT[crypto])
pip install mycelium-http-tools[fastapi,signature]

# Development (all extras + tooling)
pip install mycelium-http-tools[dev,fastapi,signature]
```

## Core usage

```python
from myc_http_tools.functions import decode_and_decompress_profile_from_base64

profile = decode_and_decompress_profile_from_base64(header_value)

related_accounts = (
    profile
    .with_read_access()
    .on_tenant(tenant_id)
    .with_roles(["admin"])
    .on_account(account_id)
    .get_related_account_or_error()
)
```

Every filter method returns a copy — the original `Profile` is never mutated.

`decode_and_decompress_profile_from_base64` raises `ProfileDecodingError` on any failure
(empty input, invalid Base64, failed decompression, or invalid JSON). It is strict by
default; pass `strict=False` to fall back to treating the payload as uncompressed (useful
in development). To produce a header value (e.g. in tests), use the encode counterpart:

```python
from myc_http_tools.functions import compress_and_encode_profile_to_base64

encoded = compress_and_encode_profile_to_base64(profile)  # requires the zstandard extra
```

## FastAPI usage

Install with the `fastapi` extra, then choose one of three integration styles.

### Dependency injection (recommended)

```python
from fastapi import FastAPI, Depends
from myc_http_tools.models.profile import Profile
from myc_http_tools.fastapi import (
    get_profile_from_header,
    get_profile_from_header_required,
)

app = FastAPI()

# Optional profile (None if the header is missing in development)
@app.get("/whoami")
async def whoami(profile: Profile | None = Depends(get_profile_from_header)):
    return {"accId": str(profile.acc_id) if profile else None}

# Required profile (raises if the header is missing/undecodable)
@app.get("/admin")
async def admin(profile: Profile = Depends(get_profile_from_header_required)):
    profile.has_admin_privileges_or_error()
    return {"accId": str(profile.acc_id)}
```

### Middleware

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from myc_http_tools.fastapi import profile_middleware

app = FastAPI()
app.add_middleware(BaseHTTPMiddleware, dispatch=profile_middleware)

@app.get("/whoami")
async def whoami(request: Request):
    profile = request.state.profile  # from the x-mycelium-profile header
    return {"accId": str(profile.acc_id) if profile else None}
```

### Manual extraction

```python
from fastapi import FastAPI, Request
from myc_http_tools.fastapi import get_profile_from_request

app = FastAPI()

@app.get("/whoami")
async def whoami(request: Request):
    profile = get_profile_from_request(request)
    return {"accId": str(profile.acc_id) if profile else None}
```

The DI and middleware helpers are environment-gated: in development a missing/invalid
header resolves to `None`; in production a missing header responds `403` and an undecodable
header `401`. The environment is read from the `ENVIRONMENT` variable (default
`development`).

## Profile signature verification (opt-in)

When the gateway is configured with `[core.profileSigning]`, it adds
`x-mycelium-profile-signature` to every request that carries
`x-mycelium-profile`: a compact JWS (`alg: EdDSA`, `kid: <key version>`) over
`{iat, ph, aud}`, where `ph` is the SHA-256 of the exact profile header and
`aud` the downstream service name. The gateway publishes its public keys as a
JWKS at `/.well-known/mycelium-profile-jwks.json`; this SDK downloads them,
caches them and verifies every signature locally.

> **Rollout order is mandatory.** Confirm the gateway in front of this service
> is already signing **before** setting `MYCELIUM_JWKS_URL` here. A service
> that verifies behind a gateway that does not sign rejects every request
> (403). To roll back, unset `MYCELIUM_JWKS_URL` here first, then disable
> signing in the gateway.

Enable it by installing the `signature` extra and pointing the SDK at the
gateway JWKS:

```bash
export MYCELIUM_JWKS_URL="https://gateway.internal/.well-known/mycelium-profile-jwks.json"
# Required with MYCELIUM_JWKS_URL: this service's name as registered in the gateway
export MYC_PROFILE_SIGNATURE_AUDIENCE=billing-api
# Optional: accepted clock skew, both directions (default 60 seconds)
export MYC_PROFILE_SIGNATURE_TOLERANCE_SECONDS=60
# Local development only: accept an http:// JWKS URL (logs a warning)
# export MYCELIUM_JWKS_ALLOW_INSECURE_HTTP=true
```

Configure at startup so a misconfigured service never starts.
`configure_profile_signature()` validates the settings; the JWKS is downloaded
on the **first signed request**, and requests fail closed (403) until it is
available. Requests only reach this service through the gateway, so the
gateway is up when that first request arrives: the service never depends on
the gateway to start (both can start in any order). Pass
`prefetch=True` to download the keys at startup instead (blocking, at most
5 seconds; raises `ProfileJwksFetchError` when the gateway is unreachable).
Without `configure_profile_signature()` the settings are loaded on first use
and invalid settings make requests fail with 500:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from myc_http_tools import configure_profile_signature

@asynccontextmanager
async def lifespan(app):
    # raises ProfileSignatureConfigurationError (invalid settings);
    # the keys are downloaded on the first signed request
    configure_profile_signature()
    yield

app = FastAPI(lifespan=lifespan)
```

With `MYCELIUM_JWKS_URL` set, the four FastAPI entry points
(`get_profile_from_request`, `profile_middleware`,
`get_profile_from_header`, `get_profile_from_header_required`) verify before
decoding and answer **403** `Unable to verify Mycelium profile` on any
signature rejection, **in every `ENVIRONMENT`**: the development leniency never applies to
a failed signature. Duplicate profile/signature headers are rejected. Without
that variable nothing changes, except that a signed profile logs one warning
per process (`MYCELIUM_JWKS_URL` is not set, so nothing is verified). The
required header dependency preserves FastAPI 422 when the profile header is
absent. Internal/configuration errors return generic 500 and never run the
handler.

Key handling follows the gateway contract (`jwks-vectors.json`):

- the set is cached for the `max-age` sent by the gateway (bounded to
  1 minute..1 day, 12 hours when absent), then refreshed;
- a signature with an unknown `kid` triggers one refetch, at most every
  30 seconds, so gateway key rotation needs no change or restart here;
- until a first set is downloaded, a failed attempt is retried after
  5 seconds, so a service started before the gateway recovers quickly;
- if a refresh fails, the last valid set is kept and the failure is logged
  (standard `logging`);
- the fetch is bounded (5 seconds in total, 64 KiB, redirects never followed)
  and a set with private material, another key type, a wrong key length or
  a non-canonical/repeated `kid` is refused as a whole.

Any present but invalid setting (non-`https` URL without the development
switch, URL with credentials, missing audience, invalid tolerance, a value
other than `true`/`false` for the switch, missing `signature` extra) is a
configuration error, never "verification disabled". Tolerance must be a
positive integer <= 9007199254740991, matching the other SDKs. The JWKS URL
comes only from configuration, never from a request.

Custom integrations can call the verifier directly; the raw decoder
`decode_and_decompress_profile_from_base64` does **not** verify anything:

```python
from myc_http_tools import load_profile_signature_verifier_from_env

verifier = load_profile_signature_verifier_from_env()  # once, at startup
if verifier is None:
    raise RuntimeError("Profile verification must be configured for this service")
# optional: download the keys now (raises ProfileJwksFetchError);
# otherwise they are downloaded on the first verify_and_decode call
verifier.prefetch()
profile = verifier.verify_and_decode(profile_header, signature_header)
```

`verify_and_decode` may block while keys are (re)fetched; call it from a
worker thread in async code.

Limits (by design): a captured valid pair can be replayed to the same service
during the tolerance window; only `x-mycelium-profile` is signed, so derive
identity from the profile, not from `x-mycelium-email`/`x-mycelium-role`
alone. Mount the middleware only where a profile is required: public or
health routes do not receive a profile from the gateway.

## Error handling

All SDK errors extend `MyceliumError` (`message`, `code`, `exp_true`):

| Error | Code | Raised by |
|---|---|---|
| `ProfileSignatureError` | `MYC_PROFILE_SIGNATURE_INVALID` | `verify_profile_signature` / `verify_and_decode_profile` (carries a log-safe `reason`) |
| `ProfileSignatureConfigurationError` | `MYC_PROFILE_SIGNATURE_CONFIG_INVALID` | Invalid `MYCELIUM_JWKS_*` / `MYC_PROFILE_SIGNATURE_*` setting, or an unsafe JWKS |
| `ProfileJwksFetchError` | `MYC_PROFILE_JWKS_FETCH_FAILED` | The gateway JWKS could not be downloaded (`prefetch=True` at startup: abort) |
| `ProfileDecodingError` | `MYC00020` | `decode_and_decompress_profile_from_base64` on any decode failure |
| `InsufficientLicensesError` | `MYC00019` | `get_related_account_or_error()` when licensed resources are present but empty |
| `InsufficientPrivilegesError` | `MYC00019` | Any method requiring a privilege the profile lacks (carries `filtering_state`) |

## License

Apache-2.0
