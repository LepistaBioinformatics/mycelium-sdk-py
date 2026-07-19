"""Tests for the Profile method surface added for parity with the gateway/JS SDK."""

from uuid import UUID

import pytest

from myc_http_tools.exceptions import (
    InsufficientLicensesError,
    InsufficientPrivilegesError,
)
from myc_http_tools.models.licensed_resources import (
    LicensedResource,
    LicensedResources,
)
from myc_http_tools.models.owner import Owner, redact_email
from myc_http_tools.models.permission import Permission
from myc_http_tools.models.profile import Profile
from myc_http_tools.models.related_accounts import (
    AllowedAccounts,
    HasManagerPrivileges,
    HasStaffPrivileges,
    HasTenantWidePrivileges,
)
from myc_http_tools.models.tenants_ownership import (
    TenantOwnership,
    TenantsOwnership,
)

TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ACC_X = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
ACC_Y = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
ROLE_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def res(tenant, acc, role, perm, permit=None, deny=None, sys_acc=False):
    return LicensedResource(
        acc_id=acc,
        sys_acc=sys_acc,
        tenant_id=tenant,
        acc_name="n",
        role=role,
        role_id=ROLE_ID,
        perm=perm,
        verified=True,
        permit_flags=permit,
        deny_flags=deny,
    )


def profile_with(*records, **kwargs):
    return Profile(
        acc_id=ACC_X,
        is_subscription=False,
        is_staff=kwargs.get("is_staff", False),
        is_manager=kwargs.get("is_manager", False),
        owner_is_active=True,
        account_is_active=True,
        account_was_approved=True,
        account_was_archived=False,
        account_was_deleted=False,
        licensed_resources=(
            LicensedResources(records=list(records)) if records else None
        ),
        tenants_ownership=kwargs.get("tenants_ownership"),
        owners=kwargs.get("owners", []),
    )


def test_redact_email():
    assert redact_email("samuel@biotrop.com.br") == "s*****@biotrop.com.br"
    assert redact_email("a@b.com") == "a*@b.com"
    assert redact_email("no-at-sign") == "no-at-sign"


def test_profile_string_and_owners():
    owner = Owner(id=ACC_Y, email="ada@example.com", is_principal=True)
    profile = profile_with(owners=[owner])
    assert profile.profile_string() == f"profile/{ACC_X}"
    assert profile.get_owners_ids() == [ACC_Y]
    assert "a**@example.com" in profile.profile_redacted()


def test_has_admin_privileges():
    assert profile_with(is_staff=True).has_admin_privileges()
    assert profile_with(is_manager=True).has_admin_privileges()
    assert not profile_with().has_admin_privileges()
    with pytest.raises(InsufficientPrivilegesError):
        profile_with().has_admin_privileges_or_error()


def test_has_permit_flags():
    r1 = res(
        TENANT_A, ACC_X, "admin", Permission.READ, permit=["beta", "gamma"]
    )
    r2 = res(TENANT_A, ACC_Y, "admin", Permission.READ)
    profile = profile_with(r1, r2)
    result = profile.has_permit_flags(["beta", "gamma"])
    records = result.licensed_resources.to_licenses_vector()
    assert len(records) == 1 and records[0].acc_id == ACC_X
    assert result.filtering_state == ["1:permittedFlags:beta,gamma"]


def test_has_not_deny_flags():
    r1 = res(TENANT_A, ACC_X, "admin", Permission.READ)
    r2 = res(TENANT_A, ACC_Y, "admin", Permission.READ, deny=["blocked"])
    profile = profile_with(r1, r2)
    result = profile.has_not_deny_flags(["blocked"])
    records = result.licensed_resources.to_licenses_vector()
    assert len(records) == 1 and records[0].acc_id == ACC_X


def test_with_system_accounts_access():
    r1 = res(TENANT_A, ACC_X, "admin", Permission.READ, sys_acc=True)
    r2 = res(TENANT_A, ACC_Y, "admin", Permission.READ)
    result = profile_with(r1, r2).with_system_accounts_access()
    records = result.licensed_resources.to_licenses_vector()
    assert len(records) == 1 and records[0].sys_acc


def test_on_tenant_as_manager_state():
    r = res(TENANT_A, ACC_X, "tenant-manager", Permission.WRITE)
    result = profile_with(r).on_tenant_as_manager(TENANT_A, Permission.WRITE)
    assert result.filtering_state == [
        f"1:tenantId:{TENANT_A}",
        "2:permission:1",
        "3:role:tenant-manager",
        "4:isTenantManager:true",
    ]


def test_with_tenant_ownership_or_error():
    ownership = TenantsOwnership(
        records=[
            TenantOwnership(id=TENANT_A, name="n", since="2026-01-01T00:00:00Z")
        ]
    )
    profile = profile_with(tenants_ownership=ownership)
    ok = profile.with_tenant_ownership_or_error(TENANT_A)
    assert ok.filtering_state == [f"1:tenantOwnership:{TENANT_A}"]
    with pytest.raises(InsufficientPrivilegesError):
        profile.with_tenant_ownership_or_error(TENANT_B)


def test_get_ids_or_error():
    profile = profile_with(res(TENANT_A, ACC_X, "admin", Permission.READ))
    assert profile.get_ids_or_error() == [ACC_X]
    # admin with no licenses -> ok empty
    assert profile_with(is_staff=True).get_ids_or_error() == []
    # no ids, no admin -> error
    with pytest.raises(InsufficientPrivilegesError):
        profile_with().get_ids_or_error()


def test_get_related_account_priority():
    assert isinstance(
        profile_with(is_staff=True).get_related_account_or_error(),
        HasStaffPrivileges,
    )
    assert isinstance(
        profile_with(is_manager=True).get_related_account_or_error(),
        HasManagerPrivileges,
    )
    allowed = profile_with(
        res(TENANT_A, ACC_X, "admin", Permission.READ)
    ).get_related_account_or_error()
    assert isinstance(allowed, AllowedAccounts) and allowed.accounts == [ACC_X]
    with pytest.raises(InsufficientLicensesError):
        Profile(
            acc_id=ACC_X,
            is_subscription=False,
            is_staff=False,
            owner_is_active=True,
            account_is_active=True,
            account_was_approved=True,
            account_was_archived=False,
            account_was_deleted=False,
            licensed_resources=LicensedResources(records=[]),
        ).get_related_account_or_error()


def test_get_tenant_wide_permission():
    # staff
    assert isinstance(
        profile_with(is_staff=True).get_tenant_wide_permission_or_error(
            TENANT_A, Permission.READ
        ),
        HasStaffPrivileges,
    )
    # ownership
    ownership = TenantsOwnership(
        records=[
            TenantOwnership(id=TENANT_A, name="n", since="2026-01-01T00:00:00Z")
        ]
    )
    ra = profile_with(
        tenants_ownership=ownership
    ).get_tenant_wide_permission_or_error(TENANT_A, Permission.READ)
    assert isinstance(ra, HasTenantWidePrivileges) and ra.tenant_id == TENANT_A
    # tenant-manager role fallback
    ra2 = profile_with(
        res(TENANT_A, ACC_X, "tenant-manager", Permission.WRITE)
    ).get_tenant_wide_permission_or_error(TENANT_A, Permission.WRITE)
    assert isinstance(ra2, HasTenantWidePrivileges)
    # none
    with pytest.raises(InsufficientPrivilegesError):
        profile_with(
            res(TENANT_A, ACC_X, "viewer", Permission.READ)
        ).get_tenant_wide_permission_or_error(TENANT_B, Permission.WRITE)


def test_get_related_accounts_or_tenant_wide_fallback():
    ra = profile_with(
        res(TENANT_A, ACC_X, "viewer", Permission.READ)
    ).get_related_accounts_or_tenant_wide_permission_or_error(
        TENANT_B, Permission.WRITE
    )
    assert isinstance(ra, AllowedAccounts)


def test_licensed_resource_perm_accepts_int():
    lr = LicensedResource.model_validate(
        {
            "accId": str(ACC_X),
            "sysAcc": False,
            "tenantId": str(TENANT_A),
            "accName": "n",
            "role": "r",
            "roleId": str(ROLE_ID),
            "perm": 1,
            "verified": True,
        }
    )
    assert lr.perm == Permission.WRITE


def test_licensed_resource_url_flags_roundtrip():
    url = (
        "t/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/a/cccccccccccccccccccccccccccccccc"
        "/r/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee?p=admin:1&s=1&v=1&n=bg=="
        "&pf=beta,gamma&df=blocked"
    )
    lr = LicensedResource.from_str(url)
    assert lr.permit_flags == ["beta", "gamma"]
    assert lr.deny_flags == ["blocked"]
    assert lr.perm == Permission.WRITE
