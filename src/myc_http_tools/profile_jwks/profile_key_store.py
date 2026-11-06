"""The gateway public keys cached by a downstream verifier.

- Fetched lazily on the first request (default) or before serving
  (``prefetch``). Until a first set is stored, failed attempts are retried
  after a few seconds instead of the full cooldown.
- Refreshed when ``max-age`` expires; a failed refresh keeps the last valid
  set and is logged, so a gateway outage never drops trusted keys.
- Refetched once when a signature names an unknown ``kid``, at most once per
  cooldown, and single-flight: concurrent requests share one fetch.

Thread-safe and blocking (the fetch uses the standard library).
"""

import logging
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from myc_http_tools.profile_jwks.fetch_profile_jwks import FetchedProfileJwks
from myc_http_tools.profile_jwks.profile_jwks_url import ProfileJwksUrl
from myc_http_tools.settings import PROFILE_JWKS_EMPTY_RETRY_SECONDS

logger = logging.getLogger(__name__)

ProfileJwksFetcher = Callable[[ProfileJwksUrl], FetchedProfileJwks]


class ProfileKeyStore:
    def __init__(
        self,
        url: ProfileJwksUrl,
        fetcher: ProfileJwksFetcher,
        cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._url = url
        self._fetcher = fetcher
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._state = threading.Lock()
        self._refresh = threading.Lock()
        self._keys: Mapping[str, Any] = MappingProxyType({})
        self._generation = 0
        self._fresh_until: Optional[float] = None
        self._last_attempt: Optional[float] = None

    @property
    def url(self) -> ProfileJwksUrl:
        return self._url

    def current(self) -> tuple[Mapping[str, Any], int]:
        """The trusted keys now, and the generation they belong to."""
        with self._state:
            return self._keys, self._generation

    def prefetch(self) -> None:
        """Fetch the set now (opt-in at startup); any failure is raised."""
        with self._refresh:
            self._fetch_and_store()

    def refresh_if_stale(self) -> None:
        """Refresh when the cached set expired (or was never fetched)."""
        with self._state:
            generation = self._generation
            is_stale = (
                self._fresh_until is None or self._clock() >= self._fresh_until
            )

        if is_stale:
            self._refresh_from(generation)

    def refresh_after_unknown_key(self, seen_generation: int) -> bool:
        """Refetch after an unknown ``kid``; ``True`` when newer keys exist."""
        return self._refresh_from(seen_generation)

    def _refresh_from(self, seen_generation: int) -> bool:
        with self._refresh:
            with self._state:
                generation = self._generation
                last_attempt = self._last_attempt

            if generation != seen_generation:
                return True

            cooling_down = (
                last_attempt is not None
                and self._clock() - last_attempt
                < self._retry_interval(generation)
            )
            if cooling_down:
                return False

            return self._try_fetch_and_store()

    def _retry_interval(self, generation: int) -> float:
        """The cooldown, shortened while no key set was ever stored, so a
        service that started before the gateway recovers within seconds."""
        if generation > 0:
            return self._cooldown

        return min(self._cooldown, PROFILE_JWKS_EMPTY_RETRY_SECONDS)

    def _try_fetch_and_store(self) -> bool:
        try:
            self._fetch_and_store()
        except Exception as error:
            logger.warning(
                "profile_signature.jwks outcome=refresh_failed type=%s "
                "reason=%s: keeping the last valid profile JWKS",
                type(error).__name__,
                getattr(error, "message", "unexpected error"),
            )
            return False

        return True

    def _fetch_and_store(self) -> None:
        with self._state:
            self._last_attempt = self._clock()

        fetched = self._fetcher(self._url)

        with self._state:
            self._keys = MappingProxyType(dict(fetched.keys))
            self._generation += 1
            self._fresh_until = self._clock() + fetched.max_age_seconds
