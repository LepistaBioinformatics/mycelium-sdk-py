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

# Development (all extras + tooling)
pip install mycelium-http-tools[dev,fastapi]
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
from fastapi.middleware.base import BaseHTTPMiddleware
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

## Error handling

All SDK errors extend `MyceliumError` (`message`, `code`, `exp_true`):

| Error | Code | Raised by |
|---|---|---|
| `ProfileDecodingError` | `MYC00020` | `decode_and_decompress_profile_from_base64` on any decode failure |
| `InsufficientLicensesError` | `MYC00019` | `get_related_account_or_error()` when licensed resources are present but empty |
| `InsufficientPrivilegesError` | `MYC00019` | Any method requiring a privilege the profile lacks (carries `filtering_state`) |

## License

Apache-2.0
