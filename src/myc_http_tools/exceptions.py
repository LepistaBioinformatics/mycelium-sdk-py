"""Custom exceptions for mycelium-http-tools."""

from typing import Optional


class MyceliumError(Exception):
    """Base exception for Mycelium HTTP Tools."""

    def __init__(
        self, message: str, code: Optional[str] = None, exp_true: bool = False
    ):
        self.message = message
        self.code = code
        self.exp_true = exp_true
        super().__init__(self.message)


class InsufficientPrivilegesError(MyceliumError):
    """Raised when there are insufficient privileges to perform an action."""

    def __init__(
        self, message: str, filtering_state: Optional[list[str]] = None
    ):
        self.filtering_state = filtering_state or []
        super().__init__(message=message, code="MYC00019", exp_true=True)


class InsufficientLicensesError(MyceliumError):
    """Raised when there are insufficient licenses to perform an action."""

    def __init__(
        self, message: str = "Insufficient licenses to perform these action"
    ):
        super().__init__(message=message, code="MYC00019", exp_true=True)


class ProfileDecodingError(MyceliumError):
    """Raised when there is an error decoding or decompressing a profile."""

    def __init__(self, message: str):
        super().__init__(message=message, code="MYC00020", exp_true=False)


PROFILE_SIGNATURE_INVALID_CODE = "MYC_PROFILE_SIGNATURE_INVALID"

PROFILE_SIGNATURE_CONFIG_INVALID_CODE = "MYC_PROFILE_SIGNATURE_CONFIG_INVALID"

PROFILE_JWKS_FETCH_FAILED_CODE = "MYC_PROFILE_JWKS_FETCH_FAILED"


class ProfileSignatureConfigurationError(MyceliumError):
    """Raised when the profile signature verification configuration is invalid.

    ``MYCELIUM_JWKS_URL`` means "verification requested": a malformed setting
    (or an unsafe JWKS document) must stop the service instead of silently
    disabling verification. The message names variables, never their values.
    """

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code=PROFILE_SIGNATURE_CONFIG_INVALID_CODE,
            exp_true=False,
        )


class ProfileSignatureError(MyceliumError):
    """Raised when a profile signature fails verification.

    ``reason`` is a stable, log-safe identifier (for example
    ``timestamp_out_of_tolerance``). It must not be returned to clients:
    HTTP integrations answer with a generic message.
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            message=f"Profile signature rejected: {reason}",
            code=PROFILE_SIGNATURE_INVALID_CODE,
            exp_true=True,
        )


class ProfileJwksFetchError(MyceliumError):
    """Raised when the gateway profile JWKS cannot be downloaded.

    With ``prefetch=True`` at startup it aborts the service. Otherwise a failed
    download is logged: requests fail closed until a first key set is stored,
    and a failed refresh keeps the last valid set.
    """

    def __init__(self, problem: str):
        super().__init__(
            message=f"profile_jwks_fetch_failed: {problem}",
            code=PROFILE_JWKS_FETCH_FAILED_CODE,
            exp_true=False,
        )
