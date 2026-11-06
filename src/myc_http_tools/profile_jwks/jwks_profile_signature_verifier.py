"""Downstream verifier whose trusted keys come from the gateway JWKS.

Enabled by ``MYCELIUM_JWKS_URL``; ``MYC_PROFILE_SIGNATURE_AUDIENCE`` is then
required, so a signed pair issued for another service is always refused. The
verification itself is the shared, local contract; only the keys are remote,
refreshed as described in ``ProfileKeyStore``.
"""

from typing import Optional

from myc_http_tools.exceptions import ProfileSignatureError
from myc_http_tools.functions.verify_profile_signature import (
    verify_and_decode_profile,
)
from myc_http_tools.models.profile import Profile
from myc_http_tools.profile_jwks.profile_key_store import ProfileKeyStore
from myc_http_tools.profile_jwks.read_signature_key_version import (
    read_signature_key_version,
)
from myc_http_tools.profile_signature_verifier import ProfileSignatureVerifier


class JwksProfileSignatureVerifier:
    def __init__(
        self,
        store: ProfileKeyStore,
        tolerance_seconds: int,
        expected_audience: str,
    ):
        self._store = store
        self.tolerance_seconds = tolerance_seconds
        self.expected_audience = expected_audience

    @property
    def store(self) -> ProfileKeyStore:
        return self._store

    def prefetch(self) -> None:
        """Opt-in: download the key set now; failures are raised."""
        self._store.prefetch()

    def verify_and_decode(
        self,
        profile_header: str,
        signature_header: str,
        *,
        now_seconds: Optional[int] = None,
    ) -> Profile:
        """Verify the signed profile, refetching once on an unknown ``kid``.

        Blocking when the keys must be (re)fetched.
        """
        self._store.refresh_if_stale()
        _, generation = self._store.current()

        try:
            return self._verify_with_current_keys(
                profile_header, signature_header, now_seconds
            )
        except ProfileSignatureError as error:
            if not self._refreshed_for_unknown_key(
                error, signature_header, generation
            ):
                raise

        return self._verify_with_current_keys(
            profile_header, signature_header, now_seconds
        )

    def _refreshed_for_unknown_key(
        self,
        error: ProfileSignatureError,
        signature_header: str,
        generation: int,
    ) -> bool:
        """Only an unknown but canonical ``kid`` justifies network work."""
        return (
            error.reason == "unknown_key"
            and read_signature_key_version(signature_header) is not None
            and self._store.refresh_after_unknown_key(generation)
        )

    def _verify_with_current_keys(
        self,
        profile_header: str,
        signature_header: str,
        now_seconds: Optional[int],
    ) -> Profile:
        keys, _ = self._store.current()
        verifier = ProfileSignatureVerifier(
            public_keys=keys,
            tolerance_seconds=self.tolerance_seconds,
            expected_audience=self.expected_audience,
        )

        return verify_and_decode_profile(
            profile_header, signature_header, verifier, now_seconds=now_seconds
        )
