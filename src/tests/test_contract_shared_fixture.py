"""Contract test decoding the shared gateway fixture.

The fixture at src/tests/mock/large-profile.json is shared byte-for-byte with
the Go SDK contract test (mycelium-sdk-go/testdata/large-profile.json). It is the
canonical wire JSON the gateway emits: camelCase keys, perm as "read"/"write",
Records form.
"""

import base64
import os
from uuid import UUID

import zstandard as zstd

from myc_http_tools.functions import (
    compress_and_encode_profile_to_base64,
    decode_and_decompress_profile_from_base64,
)
from myc_http_tools.models.profile import Profile
from myc_http_tools.models.related_accounts import HasManagerPrivileges

FIXTURE = os.path.join(os.path.dirname(__file__), "mock", "large-profile.json")
FIXTURE_ACC_ID = UUID("5490dc55-60a2-4049-bfa3-8bedd21fd68a")
FIXTURE_TENANT_ID = UUID("17fe5508-462f-45f9-bcf0-8ddd80547833")
FIXTURE_RECORDS = 131


def _read_fixture_bytes() -> bytes:
    with open(FIXTURE, "rb") as handle:
        return handle.read()


def test_decode_gateway_encoded_fixture():
    raw = _read_fixture_bytes()
    # Emulate the gateway header: JSON -> ZSTD -> Base64.
    compressed = zstd.ZstdCompressor(level=3).compress(raw)
    encoded = base64.standard_b64encode(compressed).decode("utf-8")

    profile = decode_and_decompress_profile_from_base64(encoded)

    assert profile.acc_id == FIXTURE_ACC_ID
    assert profile.is_manager is True
    assert profile.is_staff is False
    assert len(profile.owners) == 1
    assert profile.owners[0].email == "user@biotrop.com.br"

    records = profile.licensed_resources.to_licenses_vector()
    assert len(records) == FIXTURE_RECORDS

    ownerships = profile.tenants_ownership.to_ownership_vector()
    assert len(ownerships) == 1
    assert ownerships[0].id == FIXTURE_TENANT_ID


def test_methods_on_fixture():
    profile = Profile.model_validate_json(_read_fixture_bytes())

    # Manager profile resolves to manager privileges.
    assert isinstance(
        profile.get_related_account_or_error(), HasManagerPrivileges
    )

    # Scoping to the fixture tenant retains records.
    scoped = profile.on_tenant(FIXTURE_TENANT_ID)
    assert scoped.licensed_resources is not None
    assert len(scoped.licensed_resources.to_licenses_vector()) > 0

    # Tenant ownership is recognized.
    profile.with_tenant_ownership_or_error(FIXTURE_TENANT_ID)


def test_encode_roundtrip_fixture():
    profile = Profile.model_validate_json(_read_fixture_bytes())
    encoded = compress_and_encode_profile_to_base64(profile)
    back = decode_and_decompress_profile_from_base64(encoded)
    assert back.acc_id == profile.acc_id
    assert len(back.licensed_resources.to_licenses_vector()) == FIXTURE_RECORDS


def test_encode_emits_perm_as_string():
    profile = Profile.model_validate_json(_read_fixture_bytes())
    encoded = compress_and_encode_profile_to_base64(profile)
    decoded = base64.standard_b64decode(encoded)
    json_bytes = zstd.ZstdDecompressor().decompress(decoded)
    assert b'"perm":"write"' in json_bytes or b'"perm":"read"' in json_bytes
