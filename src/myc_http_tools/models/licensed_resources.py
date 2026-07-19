import base64
from typing import Optional, Self
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from .permission import Permission


class LicensedResource(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    acc_id: UUID
    sys_acc: bool
    tenant_id: UUID
    acc_name: str
    role: str
    role_id: UUID
    perm: Permission
    verified: bool
    permit_flags: Optional[list[str]] = Field(default=None)
    deny_flags: Optional[list[str]] = Field(default=None)

    @field_validator("perm", mode="before")
    @classmethod
    def _coerce_perm(cls, value: object) -> object:
        """Accept perm as the wire string ("read"/"write") or as the integer
        form (0/1) used in the URL representation, matching the gateway and the
        Go SDK."""
        if isinstance(value, int) and not isinstance(value, bool):
            return Permission.from_i32(value)
        return value

    # --------------------------------------------------------------------------
    # PRIVATE METHODS
    # --------------------------------------------------------------------------

    @staticmethod
    def _is_uuid(value: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            UUID(value)
            return True
        except ValueError:
            return False

    # --------------------------------------------------------------------------
    # PUBLIC METHODS
    # --------------------------------------------------------------------------

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Parse a licensed resource from a URL string.

        Expected URL format: t/{tenant_id}/a/{acc_id}/r/{role_id}?p={role}:{perm}&s={0|1}&v={0|1}&n={base64_encoded_name}
        """
        # Construct full URL with localhost.local domain
        full_url = f"https://localhost.local/{value}"

        try:
            # Parse the URL
            parsed_url = urlparse(full_url)
        except Exception as e:
            raise ValueError(f"Unexpected error on check license URL: {e}")

        # Extract path segments
        path_segments = [seg for seg in parsed_url.path.split("/") if seg]

        if (
            len(path_segments) != 6
            or path_segments[0] != "t"
            or path_segments[2] != "a"
            or path_segments[4] != "r"
        ):
            raise ValueError("Invalid path format")

        tenant_id = path_segments[1]
        account_id = path_segments[3]
        role_id = path_segments[5]

        # Validate UUIDs
        if not cls._is_uuid(tenant_id):
            raise ValueError("Invalid tenant UUID")

        if not cls._is_uuid(account_id):
            raise ValueError("Invalid account UUID")

        if not cls._is_uuid(role_id):
            raise ValueError("Invalid role UUID")

        # Parse query parameters
        query_params = parse_qs(parsed_url.query)

        # Extract permissioned role (p parameter)
        if "p" not in query_params:
            raise ValueError("Parameter permissions not found")

        permissioned_role = query_params["p"][0]
        permissioned_role_parts = permissioned_role.split(":")

        if len(permissioned_role_parts) != 2:
            raise ValueError("Invalid permissioned role format")

        role_name = permissioned_role_parts[0]
        permission_code = permissioned_role_parts[1]

        # Extract system account flag (s parameter)
        if "s" not in query_params:
            raise ValueError("Parameter sys not found")

        try:
            sys_value = int(query_params["s"][0])
            if sys_value == 0:
                sys_acc = False
            elif sys_value == 1:
                sys_acc = True
            else:
                raise ValueError("Invalid account standard")
        except ValueError as e:
            if "Invalid account standard" in str(e):
                raise
            raise ValueError("Failed to parse account standard")

        # Extract verification flag (v parameter)
        if "v" not in query_params:
            raise ValueError("Parameter v not found")

        try:
            verified_value = int(query_params["v"][0])
            if verified_value == 0:
                verified = False
            elif verified_value == 1:
                verified = True
            else:
                raise ValueError("Invalid account verification")
        except ValueError as e:
            if "Invalid account verification" in str(e):
                raise
            raise ValueError("Failed to parse account verification")

        # Extract and decode account name (n parameter)
        if "n" not in query_params:
            raise ValueError("Parameter name not found")

        name_encoded = query_params["n"][0]

        try:
            name_decoded = base64.b64decode(name_encoded).decode("utf-8")
        except Exception:
            raise ValueError("Failed to decode account name")

        # Extract optional permit/deny flags (pf/df parameters)
        permit_flags = None
        if "pf" in query_params and query_params["pf"][0]:
            permit_flags = query_params["pf"][0].split(",")

        deny_flags = None
        if "df" in query_params and query_params["df"][0]:
            deny_flags = query_params["df"][0].split(",")

        # Create and return the LicensedResource instance
        return cls(
            tenant_id=UUID(tenant_id),
            acc_id=UUID(account_id),
            role_id=UUID(role_id),
            role=role_name,
            perm=Permission.from_i32(int(permission_code)),
            sys_acc=sys_acc,
            acc_name=name_decoded,
            verified=verified,
            permit_flags=permit_flags,
            deny_flags=deny_flags,
        )


class LicensedResources(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    records: Optional[list[LicensedResource]] = Field(default=None)
    urls: Optional[list[str]] = Field(default=None)

    # --------------------------------------------------------------------------
    # PUBLIC METHODS
    # --------------------------------------------------------------------------

    def to_licenses_vector(self) -> list[LicensedResource]:
        if self.records is None and self.urls is None:
            return []

        if self.records is not None:
            return self.records

        if self.urls is not None:
            return [LicensedResource.from_str(url) for url in self.urls]

        return []
