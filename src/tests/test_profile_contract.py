"""Profile ZSTD+Base64 round-trip contract test.

Verifies that a Profile constructed entirely in Python survives the
gateway's encoding pipeline (JSON → ZSTD compress → Base64) and is
faithfully reconstructed by decode_and_decompress_profile_from_base64.

No gateway binary is required. The encoding is performed in pure Python
using the same primitives (zstandard, base64, json) that the gateway uses.
"""

import base64
import json
from uuid import UUID

import zstandard as zstd

from myc_http_tools.functions import decode_and_decompress_profile_from_base64
from myc_http_tools.models.licensed_resources import LicensedResource, LicensedResources
from myc_http_tools.models.owner import Owner
from myc_http_tools.models.permission import Permission
from myc_http_tools.models.profile import Profile
from myc_http_tools.models.tenants_ownership import TenantOwnership, TenantsOwnership
from myc_http_tools.models.verbose_status import VerboseStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACC_ID = UUID("5490dc55-60a2-4049-bfa3-8bedd21fd68a")
OWNER_ID = UUID("f8676832-b9bb-4ba7-b155-4e3006172cae")
TENANT_ID = UUID("17fe5508-462f-45f9-bcf0-8ddd80547833")
RESOURCE_ACC_ID = UUID("14f0fa09-24bb-4c0e-990e-4ece32a97131")
RESOURCE_ROLE_ID = UUID("f89c7b1c-1558-4e3a-b9ac-c1374f4b412f")
TENANT_OWN_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _build_profile() -> Profile:
    """Build a realistic Profile with all optional fields populated."""
    owner = Owner(
        id=OWNER_ID,
        email="user@example.com",
        first_name="Alice",
        last_name="Smith",
        username="alice",
        is_principal=True,
    )

    resource = LicensedResource(
        acc_id=RESOURCE_ACC_ID,
        sys_acc=False,
        tenant_id=TENANT_ID,
        acc_name="FAKE_ACCOUNT_001",
        role="customer",
        role_id=RESOURCE_ROLE_ID,
        perm=Permission.WRITE,
        verified=True,
    )

    tenant_ownership = TenantOwnership(
        id=TENANT_OWN_ID,
        name="Test Tenant",
        since="2024-01-01T00:00:00Z",
    )

    return Profile(
        owners=[owner],
        acc_id=ACC_ID,
        is_subscription=False,
        is_staff=False,
        is_manager=True,
        owner_is_active=True,
        account_is_active=True,
        account_was_approved=True,
        account_was_archived=False,
        account_was_deleted=False,
        verbose_status=VerboseStatus.VERIFIED,
        licensed_resources=LicensedResources(records=[resource]),
        tenants_ownership=TenantsOwnership(records=[tenant_ownership]),
        meta={"source": "contract-test"},
    )


def _encode_profile(profile: Profile) -> str:
    """Mirrors the gateway's encoding: JSON → ZSTD compress → Base64."""
    profile_json = profile.model_dump_json(by_alias=True)
    compressor = zstd.ZstdCompressor()
    compressed = compressor.compress(profile_json.encode("utf-8"))
    return base64.standard_b64encode(compressed).decode("ascii")


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestProfileContract:
    """Round-trip contract: gateway encoding ↔ SDK decoding."""

    def test_roundtrip_top_level_scalar_fields(self):
        """All boolean and UUID fields survive the full encode/decode cycle."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert decoded.acc_id == ACC_ID
        assert decoded.is_subscription is False
        assert decoded.is_staff is False
        assert decoded.is_manager is True
        assert decoded.owner_is_active is True
        assert decoded.account_is_active is True
        assert decoded.account_was_approved is True
        assert decoded.account_was_archived is False
        assert decoded.account_was_deleted is False

    def test_roundtrip_verbose_status(self):
        """VerboseStatus enum is serialised and deserialised correctly."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert decoded.verbose_status == VerboseStatus.VERIFIED

    def test_roundtrip_owner_fields(self):
        """Owner sub-model fields (including camelCase aliases) are preserved."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert len(decoded.owners) == 1
        owner = decoded.owners[0]
        assert owner.id == OWNER_ID
        assert owner.email == "user@example.com"
        assert owner.first_name == "Alice"
        assert owner.last_name == "Smith"
        assert owner.username == "alice"
        assert owner.is_principal is True

    def test_roundtrip_licensed_resource_fields(self):
        """LicensedResource sub-model fields are preserved end-to-end."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert decoded.licensed_resources is not None
        records = decoded.licensed_resources.to_licenses_vector()
        assert len(records) == 1

        resource = records[0]
        assert resource.acc_id == RESOURCE_ACC_ID
        assert resource.sys_acc is False
        assert resource.tenant_id == TENANT_ID
        assert resource.acc_name == "FAKE_ACCOUNT_001"
        assert resource.role == "customer"
        assert resource.role_id == RESOURCE_ROLE_ID
        assert resource.perm == Permission.WRITE
        assert resource.verified is True

    def test_roundtrip_tenants_ownership(self):
        """TenantsOwnership sub-model fields are preserved end-to-end."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert decoded.tenants_ownership is not None
        assert decoded.tenants_ownership.records is not None
        assert len(decoded.tenants_ownership.records) == 1

        record = decoded.tenants_ownership.records[0]
        assert record.id == TENANT_OWN_ID
        assert record.name == "Test Tenant"
        assert record.since == "2024-01-01T00:00:00Z"

    def test_roundtrip_meta(self):
        """Arbitrary meta dict is preserved."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert decoded.meta == {"source": "contract-test"}

    def test_roundtrip_full_json_equality(self):
        """Full JSON serialisation of original and decoded profiles is identical."""
        original = _build_profile()
        decoded = decode_and_decompress_profile_from_base64(_encode_profile(original))

        assert original.model_dump_json(by_alias=True) == decoded.model_dump_json(by_alias=True)

    def test_bytes_input_accepted(self):
        """The decode function accepts bytes as well as str."""
        original = _build_profile()
        encoded_str = _encode_profile(original)
        decoded = decode_and_decompress_profile_from_base64(encoded_str.encode("utf-8"))

        assert decoded.acc_id == ACC_ID

    def test_minimal_profile_roundtrip(self):
        """A profile with only required fields and no optionals also round-trips cleanly."""
        minimal = Profile(
            owners=[],
            acc_id=ACC_ID,
            is_subscription=True,
            is_staff=True,
            owner_is_active=False,
            account_is_active=False,
            account_was_approved=False,
            account_was_archived=False,
            account_was_deleted=False,
        )

        decoded = decode_and_decompress_profile_from_base64(_encode_profile(minimal))

        assert decoded.acc_id == ACC_ID
        assert decoded.is_subscription is True
        assert decoded.is_staff is True
        assert decoded.licensed_resources is None
        assert decoded.tenants_ownership is None
        assert decoded.verbose_status is None
        assert decoded.meta is None

    def test_camel_case_serialisation_contract(self):
        """Encoded JSON uses camelCase keys (matching gateway serialisation format)."""
        original = _build_profile()
        encoded = _encode_profile(original)

        # Decode base64 and ZSTD to inspect raw JSON
        raw_bytes = base64.standard_b64decode(encoded.encode("ascii"))
        decompressor = zstd.ZstdDecompressor()
        raw_json = decompressor.decompress(raw_bytes).decode("utf-8")
        payload = json.loads(raw_json)

        # Top-level gateway keys are camelCase
        assert "accId" in payload
        assert "isSubscription" in payload
        assert "isStaff" in payload
        assert "isManager" in payload
        assert "ownerIsActive" in payload
        assert "accountIsActive" in payload
        assert "accountWasApproved" in payload
        assert "accountWasArchived" in payload
        assert "accountWasDeleted" in payload
        # snake_case keys must NOT appear at top level
        assert "acc_id" not in payload
        assert "is_subscription" not in payload
