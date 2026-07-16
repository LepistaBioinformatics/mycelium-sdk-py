from typing import Callable, Optional, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from myc_http_tools.exceptions import (
    InsufficientLicensesError,
    InsufficientPrivilegesError,
)
from myc_http_tools.models.licensed_resources import (
    LicensedResource,
    LicensedResources,
)
from myc_http_tools.models.owner import Owner
from myc_http_tools.models.permission import Permission
from myc_http_tools.models.related_accounts import (
    RelatedAccounts,
    AllowedAccounts,
    HasStaffPrivileges,
    HasManagerPrivileges,
    HasTenantWidePrivileges,
)
from myc_http_tools.models.tenants_ownership import TenantsOwnership
from myc_http_tools.models.verbose_status import VerboseStatus

# Role name checked by on_tenant_as_manager, matching the gateway's
# SystemActor::TenantManager.
ROLE_TENANT_MANAGER = "tenant-manager"


class Profile(BaseModel):
    """The authenticated identity context injected by the gateway.

    The fluent filter methods return copies (the instance is never mutated),
    matching the immutable-chain semantics of the Rust gateway and sibling SDKs.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    # --------------------------------------------------------------------------
    # PUBLIC ATTRIBUTES
    # --------------------------------------------------------------------------

    owners: list[Owner] = Field(default_factory=list)
    acc_id: UUID
    is_subscription: bool
    is_staff: bool
    is_manager: bool = Field(default=False)
    owner_is_active: bool
    account_is_active: bool
    account_was_approved: bool
    account_was_archived: bool
    account_was_deleted: bool
    verbose_status: Optional[VerboseStatus] = None
    licensed_resources: Optional[LicensedResources] = None
    tenants_ownership: Optional[TenantsOwnership] = None
    meta: Optional[dict] = None
    filtering_state: Optional[list[str]] = None

    # --------------------------------------------------------------------------
    # STRING / IDENTITY HELPERS
    # --------------------------------------------------------------------------

    def profile_string(self) -> str:
        """Return a stable "profile/<accId>" identifier."""
        return f"profile/{self.acc_id}"

    def profile_redacted(self) -> str:
        """Return the profile identifier plus owner emails with masked locals."""
        redacted = [owner.redacted_email() for owner in self.owners]
        return f"profile/{self.acc_id} owners: [{', '.join(redacted)}]"

    def get_owners_ids(self) -> list[UUID]:
        """Return the ids of the profile owners."""
        return [owner.id for owner in self.owners]

    # --------------------------------------------------------------------------
    # PRIVILEGE CHECKS
    # --------------------------------------------------------------------------

    def has_admin_privileges(self) -> bool:
        """Report whether the profile is staff or manager."""
        return self.is_staff or self.is_manager

    def has_admin_privileges_or_error(self) -> None:
        """Raise when the profile lacks administration privileges."""
        if not self.has_admin_privileges():
            raise InsufficientPrivilegesError(
                "Current account has no administration privileges",
                filtering_state=self.filtering_state,
            )

    # --------------------------------------------------------------------------
    # FLAG FILTERS
    # --------------------------------------------------------------------------

    def has_permit_flags(self, flags: list[str]) -> Self:
        """Keep resources whose permit_flags contain ALL the given flags."""
        flags = [str(flag) for flag in flags]

        def predicate(resource: LicensedResource) -> bool:
            if resource.permit_flags is None:
                return False
            return all(flag in resource.permit_flags for flag in flags)

        return self.__apply_filter(predicate, "permittedFlags", ",".join(flags))

    def has_not_deny_flags(self, flags: list[str]) -> Self:
        """Keep resources with NONE of the given flags in their deny_flags."""
        flags = [str(flag) for flag in flags]

        def predicate(resource: LicensedResource) -> bool:
            if resource.deny_flags is None:
                return True
            return not any(flag in resource.deny_flags for flag in flags)

        return self.__apply_filter(predicate, "deniedFlags", ",".join(flags))

    # --------------------------------------------------------------------------
    # SCOPING FILTERS
    # --------------------------------------------------------------------------

    def on_tenant(self, tenant_id: UUID) -> Self:
        """Keep resources scoped to the given tenant."""
        return self.__apply_filter(
            lambda r: r.tenant_id == tenant_id, "tenantId", str(tenant_id)
        )

    def on_tenant_as_manager(
        self, tenant_id: UUID, permission: Permission
    ) -> Self:
        """Scope to the tenant with the given permission and manager role."""
        profile = (
            self.on_tenant(tenant_id)
            .__with_permission(permission)
            .with_roles([ROLE_TENANT_MANAGER])
        )
        return profile.model_copy(
            update={
                "filtering_state": profile.__next_state(
                    "isTenantManager", "true"
                )
            }
        )

    def on_account(self, account_id: UUID) -> Self:
        """Keep resources scoped to the given account."""
        return self.__apply_filter(
            lambda r: r.acc_id == account_id, "accountId", str(account_id)
        )

    def with_system_accounts_access(self) -> Self:
        """Keep resources belonging to system accounts."""
        return self.__apply_filter(lambda r: r.sys_acc, "isAccStd", "true")

    # --------------------------------------------------------------------------
    # PERMISSION / ROLE FILTERS
    # --------------------------------------------------------------------------

    def with_read_access(self) -> Self:
        """Keep resources granting at least read permission."""
        return self.__with_permission(Permission.READ)

    def with_write_access(self) -> Self:
        """Keep resources granting write permission."""
        return self.__with_permission(Permission.WRITE)

    def with_roles(self, roles: list[str]) -> Self:
        """Keep resources whose role is in the given list."""
        return self.__apply_filter(
            lambda r: r.role in roles, "role", ",".join(roles)
        )

    # --------------------------------------------------------------------------
    # OWNERSHIP
    # --------------------------------------------------------------------------

    def with_tenant_ownership_or_error(self, tenant_id: UUID) -> Self:
        """Return a filtered profile when it owns the tenant, else raise."""
        if self.tenants_ownership is not None:
            for tenant in self.tenants_ownership.to_ownership_vector():
                if tenant.id == tenant_id:
                    return self.model_copy(
                        update={
                            "filtering_state": self.__next_state(
                                "tenantOwnership", str(tenant_id)
                            )
                        }
                    )

        raise InsufficientPrivilegesError(
            "Insufficient privileges to perform these action "
            f"(no tenant ownership): {self.__state_str()}",
            filtering_state=self.filtering_state,
        )

    # --------------------------------------------------------------------------
    # RELATED-ACCOUNT RESOLUTION
    # --------------------------------------------------------------------------

    def get_related_account_or_error(self) -> RelatedAccounts:
        """Resolve the effective access scope.

        Checks staff and manager privileges before licensed resources.

        Raises:
            InsufficientLicensesError: When licensed resources are present but empty.
            InsufficientPrivilegesError: When no licensed resources are present.
        """
        if self.is_staff:
            return HasStaffPrivileges()

        if self.is_manager:
            return HasManagerPrivileges()

        if self.licensed_resources is not None:
            records = self.licensed_resources.to_licenses_vector()

            if not records:
                raise InsufficientLicensesError()

            account_ids = [record.acc_id for record in records]
            return AllowedAccounts(accounts=account_ids)

        raise InsufficientPrivilegesError(
            "Insufficient privileges to perform these action "
            f"(no accounts): {self.__state_str()}",
            filtering_state=self.filtering_state,
        )

    def get_tenant_wide_permission_or_error(
        self, tenant_id: UUID, permission: Permission
    ) -> RelatedAccounts:
        """Resolve tenant-wide access: staff, manager, tenant ownership, or the
        tenant-manager role fallback."""
        if self.is_staff:
            return HasStaffPrivileges()

        if self.is_manager:
            return HasManagerPrivileges()

        if self.tenants_ownership is not None:
            for tenant in self.tenants_ownership.to_ownership_vector():
                if tenant.id == tenant_id:
                    return HasTenantWidePrivileges(tenant_id=tenant_id)

        try:
            self.on_tenant_as_manager(tenant_id, permission).get_ids_or_error()
            return HasTenantWidePrivileges(tenant_id=tenant_id)
        except (InsufficientPrivilegesError, InsufficientLicensesError):
            pass

        raise InsufficientPrivilegesError(
            "Insufficient privileges to perform these action "
            f"(no tenant wide permission): {self.__state_str()}",
            filtering_state=self.filtering_state,
        )

    def get_related_accounts_or_tenant_wide_permission_or_error(
        self, tenant_id: UUID, permission: Permission
    ) -> RelatedAccounts:
        """Try tenant-wide resolution first, then account-scoped resolution."""
        try:
            return self.get_tenant_wide_permission_or_error(
                tenant_id, permission
            )
        except (InsufficientPrivilegesError, InsufficientLicensesError):
            return self.get_related_account_or_error()

    def get_ids_or_error(self) -> list[UUID]:
        """Return the account ids of the licensed resources.

        Succeeds when there is at least one id OR the profile has admin
        privileges.
        """
        ids: list[UUID] = []
        if self.licensed_resources is not None:
            ids = [
                record.acc_id
                for record in self.licensed_resources.to_licenses_vector()
            ]

        if ids or self.has_admin_privileges():
            return ids

        raise InsufficientPrivilegesError(
            "Insufficient privileges to perform these action "
            f"(no ids): {self.__state_str()}",
            filtering_state=self.filtering_state,
        )

    # --------------------------------------------------------------------------
    # PRIVATE METHODS
    # --------------------------------------------------------------------------

    def __next_state(self, key: str, value: str) -> list[str]:
        """Return a copy of the filtering state with a "<n>:<key>:<value>" entry
        appended (1-based index)."""
        state = self.filtering_state.copy() if self.filtering_state else []
        state.append(f"{len(state) + 1}:{key}:{value}")
        return state

    def __state_str(self) -> str:
        return ", ".join(self.filtering_state) if self.filtering_state else ""

    def __apply_filter(
        self,
        predicate: Callable[[LicensedResource], bool],
        key: str,
        value: str,
    ) -> Self:
        """Filter licensed resources by predicate and record the filter state.

        Follows the gateway: the state is always recorded, and an empty result
        (or an absent resource set) collapses licensed_resources to None.
        """
        licensed_resources = None
        if self.licensed_resources is not None:
            records = [
                resource
                for resource in self.licensed_resources.to_licenses_vector()
                if predicate(resource)
            ]
            if records:
                licensed_resources = LicensedResources(records=records)

        return self.model_copy(
            update={
                "licensed_resources": licensed_resources,
                "filtering_state": self.__next_state(key, value),
            }
        )

    def __with_permission(self, permission: Permission) -> Self:
        """Keep resources whose permission is at least the given level.

        Following the Rust gateway (not the older JS/Python behavior), this
        always records the filter state (no short-circuit) and collapses an
        empty result to None. The state value is the integer form.
        """
        return self.__apply_filter(
            lambda r: r.perm.to_int() >= permission.to_int(),
            "permission",
            str(permission.to_int()),
        )
