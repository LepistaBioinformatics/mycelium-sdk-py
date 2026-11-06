"""Download and parse the gateway profile JWKS over HTTP (standard library).

Bounded: 5 s for the whole request (connect, headers and body, like the
Rust, JavaScript and Go clients), 64 KiB body, redirects never followed (a
redirect could move the trust anchor to another origin), any non-2xx status
is a failure. The cache lifetime comes from ``Cache-Control: max-age``.
Blocking: async integrations run it in a worker thread.

``urllib`` timeouts apply per socket operation, so a server that answers
slowly could hold a request far longer than 5 s. The download therefore runs
in a daemon thread and the caller waits at most the deadline; the thread
also checks the deadline between body chunks and stops on its own.
"""

import queue
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from myc_http_tools.exceptions import ProfileJwksFetchError
from myc_http_tools.profile_jwks.profile_jwks_url import ProfileJwksUrl
from myc_http_tools.profile_jwks.read_jwks_cache_max_age import (
    read_jwks_cache_max_age,
)
from myc_http_tools.profile_jwks.trusted_profile_keys import (
    trusted_profile_keys_from_jwks,
)
from myc_http_tools.settings import (
    PROFILE_JWKS_FETCH_TIMEOUT_SECONDS,
    PROFILE_JWKS_MAX_BYTES,
)


@dataclass(frozen=True)
class FetchedProfileJwks:
    """A key set read from the gateway, with how long it may be cached."""

    keys: Mapping[str, Any]
    max_age_seconds: int


class _NeverRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NeverRedirect)


_BODY_CHUNK_BYTES = 8192


def _download(
    url: ProfileJwksUrl, timeout_seconds: float
) -> tuple[Any, bytes]:
    """Run the request in a daemon thread; wait at most ``timeout_seconds``."""
    outcome: "queue.Queue[Any]" = queue.Queue(maxsize=1)
    deadline = time.monotonic() + timeout_seconds
    worker = threading.Thread(
        target=_download_into,
        args=(url, deadline, timeout_seconds, outcome),
        name="mycelium-profile-jwks-fetch",
        daemon=True,
    )
    worker.start()

    try:
        result = outcome.get(timeout=timeout_seconds)
    except queue.Empty:
        raise ProfileJwksFetchError(
            f"request exceeded {timeout_seconds} s"
        ) from None

    if isinstance(result, BaseException):
        raise result
    return result


def _download_into(
    url: ProfileJwksUrl,
    deadline: float,
    timeout_seconds: float,
    outcome: "queue.Queue[Any]",
) -> None:
    try:
        outcome.put(_download_before(url, deadline, timeout_seconds))
    except BaseException as error:  # noqa: BLE001 - handed to the caller
        outcome.put(error)


def _download_before(
    url: ProfileJwksUrl, deadline: float, timeout_seconds: float
) -> tuple[Any, bytes]:
    request = urllib.request.Request(
        url.value, headers={"Accept": "application/json"}, method="GET"
    )
    try:
        with _OPENER.open(request, timeout=timeout_seconds) as response:
            if not 200 <= response.status < 300:
                raise ProfileJwksFetchError(f"status {response.status}")

            body = _read_bounded(response, deadline)
            return response.headers.get("Cache-Control"), body
    except urllib.error.HTTPError as error:
        error.close()
        raise ProfileJwksFetchError(f"status {error.code}") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise ProfileJwksFetchError(
            f"request failed: {type(error).__name__}"
        ) from error


def _read_bounded(response: Any, deadline: float) -> bytes:
    """Read at most the size limit + 1 byte, never past the deadline."""
    chunks: list[bytes] = []
    size = 0
    while size <= PROFILE_JWKS_MAX_BYTES:
        if time.monotonic() > deadline:
            raise ProfileJwksFetchError("body exceeded the deadline")

        wanted = min(_BODY_CHUNK_BYTES, PROFILE_JWKS_MAX_BYTES + 1 - size)
        chunk = response.read1(wanted)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)

    return b"".join(chunks)


def fetch_profile_jwks(
    url: ProfileJwksUrl,
    *,
    timeout_seconds: float = PROFILE_JWKS_FETCH_TIMEOUT_SECONDS,
) -> FetchedProfileJwks:
    """Fetch the set; ``ProfileJwksFetchError`` or a configuration error.

    ``timeout_seconds`` bounds the whole request; only tests change it.
    """
    cache_control, body = _download(url, timeout_seconds)
    if len(body) > PROFILE_JWKS_MAX_BYTES:
        raise ProfileJwksFetchError("body exceeds the size limit")

    return FetchedProfileJwks(
        keys=trusted_profile_keys_from_jwks(body),
        max_age_seconds=read_jwks_cache_max_age(cache_control),
    )
