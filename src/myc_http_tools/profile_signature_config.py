"""Configuration of the downstream profile signature verification.

Verification is opt-in per service: it is enabled when at least one
``MYC_PROFILE_PUBLIC_KEY_<version>`` variable is present. Nothing is read at
import time, so ``load_dotenv()`` (or any late environment setup) called after
importing this package is honored.

Two ways to obtain the process-wide verifier:

- ``configure_profile_signature()``: explicit, recommended in the application
  startup/lifespan. Raises ``ProfileSignatureConfigurationError`` so a
  misconfigured service does not start.
- ``get_profile_signature_verifier()``: used by the HTTP integrations. Loads
  lazily on first use if ``configure_profile_signature`` was never called and
  caches the outcome (verifier, disabled, or configuration error). The
  environment is never re-read per request.
"""

import os
import re
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional

from myc_http_tools.exceptions import ProfileSignatureConfigurationError
from myc_http_tools.settings import (
    DEFAULT_PROFILE_SIGNATURE_TOLERANCE_SECONDS,
    MAX_SAFE_TIMESTAMP_SECONDS,
    PROFILE_PUBLIC_KEY_ENV_PREFIX,
    PROFILE_SIGNATURE_AUDIENCE_ENV,
    PROFILE_SIGNATURE_TOLERANCE_ENV,
)

_CANONICAL_VERSION = re.compile(r"^[1-9][0-9]*$")
_MAX_KEY_VERSION = 4_294_967_295
_INSTALL_HINT = (
    "Install the optional verification dependencies with: "
    "pip install 'mycelium-http-tools[signature]'"
)


@dataclass(frozen=True)
class ProfileSignatureVerifier:
    """Immutable verification settings: trusted keys by ``kid``.

    ``public_keys`` maps the canonical key version (the JWS ``kid``) to an
    ``Ed25519PublicKey``. It is a read-only mapping.
    """

    public_keys: Mapping[str, Any]
    tolerance_seconds: int
    expected_audience: Optional[str] = None


def is_canonical_key_version(raw: str) -> bool:
    """Whether ``raw`` is a canonical positive u32 (no sign/zeros/spaces)."""
    if len(raw) > 10 or not _CANONICAL_VERSION.fullmatch(raw):
        return False

    return int(raw) <= _MAX_KEY_VERSION


def _parse_tolerance(environ: Mapping[str, str]) -> int:
    raw = environ.get(PROFILE_SIGNATURE_TOLERANCE_ENV)
    if raw is None:
        return DEFAULT_PROFILE_SIGNATURE_TOLERANCE_SECONDS

    trimmed = raw.strip()
    if (len(trimmed) > 16 or not _CANONICAL_VERSION.fullmatch(trimmed)
            or int(trimmed) > MAX_SAFE_TIMESTAMP_SECONDS):
        raise ProfileSignatureConfigurationError(
            f"{PROFILE_SIGNATURE_TOLERANCE_ENV} must be a positive integer"
        )

    return int(trimmed)


def _parse_audience(environ: Mapping[str, str]) -> Optional[str]:
    raw = environ.get(PROFILE_SIGNATURE_AUDIENCE_ENV)
    if raw is None:
        return None

    if raw.strip() == "":
        raise ProfileSignatureConfigurationError(
            f"{PROFILE_SIGNATURE_AUDIENCE_ENV} must not be empty"
        )

    return raw


def _public_key_variables(environ: Mapping[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in environ.items()
        if name.startswith(PROFILE_PUBLIC_KEY_ENV_PREFIX)
    }


def _load_public_key(name: str, pem: str) -> Any:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            load_pem_public_key,
        )
        import jwt  # noqa: F401  (required later for verification)
    except ImportError as error:
        raise ProfileSignatureConfigurationError(
            f"{name} is set but verification dependencies are missing. "
            f"{_INSTALL_HINT}"
        ) from error

    if pem.strip() == "":
        raise ProfileSignatureConfigurationError(f"{name} is empty")

    try:
        key = load_pem_public_key(pem.encode("utf-8"))
    except (ValueError, TypeError) as error:
        raise ProfileSignatureConfigurationError(
            f"{name} is not a PEM SubjectPublicKeyInfo public key "
            "(a private key or malformed PEM was provided)"
        ) from error

    if not isinstance(key, Ed25519PublicKey):
        raise ProfileSignatureConfigurationError(
            f"{name} is not an Ed25519 public key"
        )

    return key


def _load_public_keys(variables: Mapping[str, str]) -> dict[str, Any]:
    keys: dict[str, Any] = {}

    for name in sorted(variables):
        version = name[len(PROFILE_PUBLIC_KEY_ENV_PREFIX) :]
        if not is_canonical_key_version(version):
            raise ProfileSignatureConfigurationError(
                f"{name}: key version suffix must be a canonical positive "
                "integer (for example MYC_PROFILE_PUBLIC_KEY_1)"
            )

        keys[version] = _load_public_key(name, variables[name])

    return keys


def load_profile_signature_verifier_from_env(
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[ProfileSignatureVerifier]:
    """Build the verifier from an environment mapping.

    Returns ``None`` when no public key variable exists (verification
    disabled, legacy behavior). Raises ``ProfileSignatureConfigurationError``
    for any invalid entry: an invalid configuration never means "disabled".
    """
    source = os.environ if environ is None else environ

    tolerance = _parse_tolerance(source)
    audience = _parse_audience(source)
    variables = _public_key_variables(source)

    if not variables:
        return None

    return ProfileSignatureVerifier(
        public_keys=MappingProxyType(_load_public_keys(variables)),
        tolerance_seconds=tolerance,
        expected_audience=audience,
    )


# ? ---------------------------------------------------------------------------
# ? Process-wide state
# ? ---------------------------------------------------------------------------

_lock = threading.Lock()
_loaded = False
_verifier: Optional[ProfileSignatureVerifier] = None
_error: Optional[ProfileSignatureConfigurationError] = None


def _store(environ: Optional[Mapping[str, str]]) -> None:
    global _loaded, _verifier, _error

    _verifier, _error = None, None
    try:
        _verifier = load_profile_signature_verifier_from_env(environ)
    except ProfileSignatureConfigurationError as error:
        _error = error
    _loaded = True


def configure_profile_signature(
    environ: Optional[Mapping[str, str]] = None,
) -> Optional[ProfileSignatureVerifier]:
    """Load and pin the process verifier. Call it at application startup.

    Raises ``ProfileSignatureConfigurationError`` on invalid configuration so
    the service fails to start instead of serving requests.
    """
    with _lock:
        _store(environ)
        if _error is not None:
            raise _error

        return _verifier


def get_profile_signature_verifier() -> Optional[ProfileSignatureVerifier]:
    """Return the process verifier, loading it lazily once.

    Raises the cached ``ProfileSignatureConfigurationError`` on every call
    when the configuration is invalid (requests fail closed).
    """
    with _lock:
        if not _loaded:
            _store(None)

        if _error is not None:
            raise _error

        return _verifier


def reset_profile_signature_configuration() -> None:
    """Forget the cached state (tests and controlled reconfiguration only)."""
    global _loaded, _verifier, _error

    with _lock:
        _loaded, _verifier, _error = False, None, None
