"""Federated grants: the wire model and the opt-in filters.

The default chain sees local grants only; ``with_federated`` and
``from_issuer`` opt in to the grants peers asserted, mirroring the gateway.
"""

import json
from pathlib import Path
from uuid import UUID, uuid4

from myc_http_tools.functions import (
    compress_and_encode_profile_to_base64,
    decode_and_decompress_profile_from_base64,
)
from myc_http_tools.models import FederatedResource
from myc_http_tools.models.licensed_resources import (
    LicensedResource,
    LicensedResources,
)
from myc_http_tools.models.owner import Owner
from myc_http_tools.models.permission import Permission
from myc_http_tools.models.profile import Profile

ISSUER_A = UUID("77777777-7777-4777-8777-777777777777")
ISSUER_B = UUID("88888888-8888-4888-8888-888888888888")

VECTORS = Path(__file__).parent / "mock" / "profile-signature" / "vectors.json"


def grant_fields(role: str) -> dict:
    return {
        "acc_id": uuid4(),
        "sys_acc": False,
        "tenant_id": uuid4(),
        "acc_name": "account-01",
        "role": role,
        "role_id": uuid4(),
        "perm": Permission.READ,
        "verified": True,
    }


def make_profile(federated: list[FederatedResource] | None) -> Profile:
    return Profile(
        owners=[
            Owner(
                id=uuid4(),
                email="user-01@example.com",
                first_name="User",
                last_name="One",
                username="user-01",
                is_principal=True,
            )
        ],
        acc_id=uuid4(),
        is_subscription=False,
        is_staff=False,
        owner_is_active=True,
        account_is_active=True,
        account_was_approved=True,
        account_was_archived=False,
        account_was_deleted=False,
        licensed_resources=LicensedResources(
            records=[LicensedResource(**grant_fields("reader"))]
        ),
        federated_resources=federated,
    )


def federated_profile() -> Profile:
    return make_profile(
        [
            FederatedResource(issuer=ISSUER_A, **grant_fields("reader")),
            FederatedResource(issuer=ISSUER_B, **grant_fields("reader")),
        ]
    )


def count(profile: Profile) -> int:
    if profile.licensed_resources is None:
        return 0
    return len(profile.licensed_resources.to_licenses_vector())


def test_federated_resource_round_trips_with_its_issuer():
    profile = federated_profile()

    wire = json.loads(profile.model_dump_json(by_alias=True, exclude_none=True))
    first = wire["federatedResources"][0]

    assert isinstance(wire["federatedResources"], list)
    assert first["issuer"] == str(ISSUER_A)
    assert first["accId"] == str(profile.federated_resources[0].acc_id)
    assert first["perm"] == "read"
    assert "permitFlags" not in first

    back = Profile.model_validate(wire)
    assert back.federated_resources == profile.federated_resources

    encoded = compress_and_encode_profile_to_base64(profile)
    decoded = decode_and_decompress_profile_from_base64(encoded)
    assert decoded.federated_resources == profile.federated_resources


def test_federated_resources_is_absent_when_there_are_none():
    profile = make_profile(None)

    wire = json.loads(profile.model_dump_json(by_alias=True, exclude_none=True))

    assert "federatedResources" not in wire
    assert Profile.model_validate(wire).federated_resources is None


def test_the_default_chain_sees_local_grants_only():
    profile = federated_profile()

    assert count(profile.with_roles(["reader"])) == 1
    assert count(profile.with_read_access()) == 1
    assert profile.get_ids_or_error() == [
        profile.licensed_resources.to_licenses_vector()[0].acc_id
    ]


def test_with_federated_adds_every_issuers_grants():
    profile = federated_profile()

    widened = profile.with_federated()

    assert count(widened) == 3
    assert all(
        type(record) is LicensedResource
        for record in widened.licensed_resources.to_licenses_vector()
    )
    assert widened.filtering_state == ["1:withFederated:true"]
    assert count(widened.with_roles(["reader"])) == 3
    # The original profile is not mutated.
    assert count(profile) == 1


def test_with_federated_without_any_grant_is_none():
    profile = make_profile(None).model_copy(
        update={"licensed_resources": None}
    )

    assert profile.with_federated().licensed_resources is None


def test_from_issuer_keeps_that_issuers_grants_only():
    profile = federated_profile()

    narrowed = profile.from_issuer(ISSUER_A)

    assert count(narrowed) == 1
    assert (
        narrowed.licensed_resources.to_licenses_vector()[0]
        == profile.federated_resources[0].to_licensed_resource()
    )
    assert narrowed.filtering_state == [f"1:issuer:{ISSUER_A}"]


def test_from_issuer_without_matching_grants_is_none():
    assert federated_profile().from_issuer(uuid4()).licensed_resources is None
    assert make_profile(None).from_issuer(ISSUER_A).licensed_resources is None


def test_shared_vector_with_federated_resources():
    contract = json.loads(VECTORS.read_text())
    vector = next(
        v
        for v in contract["vectors"]
        if v["name"] == "valid_with_federated_resources"
    )

    profile = decode_and_decompress_profile_from_base64(
        vector["profileHeader"]
    )

    assert profile.federated_resources is not None
    assert len(profile.federated_resources) == 1
    federated = profile.federated_resources[0]
    assert federated.issuer == ISSUER_A
    assert federated.role == "federated-role"

    assert profile.with_roles(["federated-role"]).licensed_resources is None

    found = profile.with_federated().with_roles(["federated-role"])
    assert count(found) == 1
    assert found.licensed_resources.to_licenses_vector()[0].acc_id == (
        federated.acc_id
    )

    from_issuer = profile.from_issuer(ISSUER_A)
    assert count(from_issuer.with_roles(["federated-role"])) == 1
    assert from_issuer.with_roles(["local-role"]).licensed_resources is None
    assert count(profile.with_roles(["local-role"])) == 1
