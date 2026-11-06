"""Configuration of the downstream profile signature verification.

Verification is opt-in per service: it is enabled when ``MYCELIUM_JWKS_URL``
is set. The trusted keys are then downloaded from the gateway profile JWKS;
``MYC_PROFILE_SIGNATURE_AUDIENCE`` becomes required. Nothing is read at import
time, so ``load_dotenv()`` (or any late environment setup) called after
importing this package is honored.

Two ways to obtain the process-wide verifier:

- ``configure_profile_signature()``: explicit, recommended in the application
  startup/lifespan. Validates the settings and raises
  ``ProfileSignatureConfigurationError`` so a misconfigured service does not
  start. The JWKS is downloaded on the first signed request (the gateway is
  up by then), so startup never depends on the gateway; ``prefetch=True``
  downloads it at startup instead (``ProfileJwksFetchError`` on failure).
- ``get_profile_signature_verifier()``: used by the HTTP integrations. Reads
  the settings lazily on first use if ``configure_profile_signature`` was never
  called (no network; the keys are fetched on the first signed request) and
  caches the outcome (verifier, disabled, or configuration error). The
  environment is never re-read per request.
"""

import logging
import os
import re
import threading
from typing import Mapping, Optional

from myc_http_tools.exceptions import ProfileSignatureConfigurationError
from myc_http_tools.profile_jwks import (
    JwksProfileSignatureVerifier,
    ProfileJwksFetcher,
    ProfileJwksUrl,
    ProfileKeyStore,
    fetch_profile_jwks,
)
from myc_http_tools.profile_jwks.trusted_profile_keys import (
    require_verification_dependencies,
)
from myc_http_tools.profile_signature_verifier import (  # noqa: F401
    ProfileSignatureVerifier,
    is_canonical_key_version,
)
from myc_http_tools.settings import (
    DEFAULT_PROFILE_SIGNATURE_TOLERANCE_SECONDS,
    MAX_SAFE_TIMESTAMP_SECONDS,
    PROFILE_JWKS_ALLOW_INSECURE_HTTP_ENV,
    PROFILE_JWKS_REFETCH_COOLDOWN_SECONDS,
    PROFILE_JWKS_URL_ENV,
    PROFILE_SIGNATURE_AUDIENCE_ENV,
    PROFILE_SIGNATURE_TOLERANCE_ENV,
)

logger = logging.getLogger(__name__)

_CANONICAL_POSITIVE = re.compile(r"^[1-9][0-9]*$")


def _parse_tolerance(environ: Mapping[str, str]) -> int:
    raw = environ.get(PROFILE_SIGNATURE_TOLERANCE_ENV)
    if raw is None:
        return DEFAULT_PROFILE_SIGNATURE_TOLERANCE_SECONDS

    trimmed = raw.strip()
    if (
        len(trimmed) > 16
        or not _CANONICAL_POSITIVE.fullmatch(trimmed)
        or int(trimmed) > MAX_SAFE_TIMESTAMP_SECONDS
    ):
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


def _parse_insecure_switch(environ: Mapping[str, str]) -> bool:
    raw = environ.get(PROFILE_JWKS_ALLOW_INSECURE_HTTP_ENV)
    if raw is None or raw.strip() == "false":
        return False

    if raw.strip() == "true":
        return True

    raise ProfileSignatureConfigurationError(
        f"{PROFILE_JWKS_ALLOW_INSECURE_HTTP_ENV} must be true or false"
    )


def load_profile_signature_verifier_from_env(
    environ: Optional[Mapping[str, str]] = None,
    *,
    fetcher: Optional[ProfileJwksFetcher] = None,
) -> Optional[JwksProfileSignatureVerifier]:
    """Build the verifier from an environment mapping, without network.

    Returns ``None`` when ``MYCELIUM_JWKS_URL`` is absent (verification
    disabled, legacy behavior). Raises ``ProfileSignatureConfigurationError``
    for any invalid present setting, even when verification stays disabled:
    an invalid configuration never means "disabled". ``fetcher`` replaces the
    HTTP download (tests, custom transports).
    """
    source = os.environ if environ is None else environ

    tolerance = _parse_tolerance(source)
    audience = _parse_audience(source)
    allow_insecure_http = _parse_insecure_switch(source)

    raw_url = source.get(PROFILE_JWKS_URL_ENV)
    if raw_url is None:
        return None

    url = ProfileJwksUrl.parse(raw_url, allow_insecure_http)
    if audience is None:
        raise ProfileSignatureConfigurationError(
            f"{PROFILE_SIGNATURE_AUDIENCE_ENV} is required when "
            f"{PROFILE_JWKS_URL_ENV} is set"
        )

    require_verification_dependencies(PROFILE_JWKS_URL_ENV)
    store = ProfileKeyStore(
        url,
        fetcher or fetch_profile_jwks,
        PROFILE_JWKS_REFETCH_COOLDOWN_SECONDS,
    )

    return JwksProfileSignatureVerifier(store, tolerance, audience)


# ? ---------------------------------------------------------------------------
# ? Process-wide state
# ? ---------------------------------------------------------------------------

_lock = threading.Lock()
_loaded = False
_verifier: Optional[JwksProfileSignatureVerifier] = None
_error: Optional[ProfileSignatureConfigurationError] = None
_ignored_signature_warned = False


def _store(
    environ: Optional[Mapping[str, str]],
    fetcher: Optional[ProfileJwksFetcher],
) -> None:
    global _loaded, _verifier, _error

    _verifier, _error = None, None
    try:
        _verifier = load_profile_signature_verifier_from_env(
            environ, fetcher=fetcher
        )
    except ProfileSignatureConfigurationError as error:
        _error = error
    _loaded = True


def configure_profile_signature(
    environ: Optional[Mapping[str, str]] = None,
    *,
    fetcher: Optional[ProfileJwksFetcher] = None,
    prefetch: bool = False,
) -> Optional[JwksProfileSignatureVerifier]:
    """Load and pin the process verifier. Call it at application startup.

    Raises ``ProfileSignatureConfigurationError`` on invalid configuration.
    The gateway JWKS is downloaded on the first signed request (requests fail
    closed with 403 until it is available), so the service never depends on
    the gateway to start. With ``prefetch=True`` it is downloaded now instead
    and ``ProfileJwksFetchError`` is raised when the gateway is unreachable
    (blocking, up to the fetch timeout).
    """
    with _lock:
        _store(environ, fetcher)
        if _error is not None:
            raise _error

        verifier = _verifier

    if verifier is not None and prefetch:
        verifier.prefetch()

    return verifier


def get_profile_signature_verifier() -> Optional[JwksProfileSignatureVerifier]:
    """Return the process verifier, loading the settings lazily once.

    Raises the cached ``ProfileSignatureConfigurationError`` on every call
    when the configuration is invalid (requests fail closed).
    """
    with _lock:
        if not _loaded:
            _store(None, None)

        if _error is not None:
            raise _error

        return _verifier


def warn_when_signature_is_ignored(carries_signature: bool) -> None:
    """Log once per process that a signed profile arrived unverified.

    The usual cause is a service that forgot ``MYCELIUM_JWKS_URL``: the
    profile is still trusted as received, exactly as before.
    """
    global _ignored_signature_warned

    with _lock:
        if not carries_signature or _ignored_signature_warned:
            return

        _ignored_signature_warned = True

    logger.warning(
        "profile_signature.verify outcome=skipped: received a signed profile "
        "but %s is not set; the signature is not verified",
        PROFILE_JWKS_URL_ENV,
    )


def reset_profile_signature_configuration() -> None:
    """Forget the cached state (tests and controlled reconfiguration only)."""
    global _loaded, _verifier, _error, _ignored_signature_warned

    with _lock:
        _loaded, _verifier, _error = False, None, None
        _ignored_signature_warned = False
