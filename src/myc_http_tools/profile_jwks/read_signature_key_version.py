"""The canonical key version named by a signature's protected header.

Used only to decide whether an ``unknown_key`` rejection deserves a JWKS
refetch: a missing or non-canonical ``kid`` never triggers network work.
"""

import base64
import json
from typing import Optional

from myc_http_tools.profile_signature_verifier import is_canonical_key_version


def read_signature_key_version(signature_header: str) -> Optional[str]:
    protected = signature_header.split(".")[0]
    try:
        raw = base64.urlsafe_b64decode(
            (protected + "=" * (-len(protected) % 4)).encode("ascii")
        )
        header = json.loads(raw)
    except (ValueError, UnicodeError):
        return None

    kid = header.get("kid") if isinstance(header, dict) else None
    if isinstance(kid, str) and is_canonical_key_version(kid):
        return kid

    return None
