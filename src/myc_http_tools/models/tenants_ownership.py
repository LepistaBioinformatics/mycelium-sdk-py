import base64
from typing import Optional, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class TenantOwnership(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    name: str
    since: str

    @classmethod
    def from_str(cls, value: str) -> Self:
        """Parse a tenant ownership from the compact URL form
        tid/{tenant_hex}?since={rfc3339}&name={base64(name)}.
        """
        path_part, _, raw_query = value.partition("?")

        segments = [seg for seg in path_part.split("/") if seg]
        if len(segments) != 2 or segments[0] != "tid":
            raise ValueError("Invalid path format")

        try:
            tenant_uuid = UUID(segments[1])
        except ValueError:
            raise ValueError("Invalid tenant UUID")

        # Parse the query manually so Base64/RFC3339 values (which may contain
        # '+') are preserved verbatim rather than form-decoded.
        params: dict[str, str] = {}
        for pair in raw_query.split("&"):
            if not pair:
                continue
            key, _, val = pair.partition("=")
            params[key] = val

        if "since" not in params:
            raise ValueError("Parameter since not found")

        if "name" not in params:
            raise ValueError("Parameter name not found")

        try:
            name_decoded = base64.b64decode(params["name"]).decode("utf-8")
        except Exception:
            raise ValueError("Failed to decode tenant name")

        return cls(id=tenant_uuid, name=name_decoded, since=params["since"])


class TenantsOwnership(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    records: Optional[list[TenantOwnership]] = Field(default=None)
    urls: Optional[list[str]] = Field(default=None)

    def to_ownership_vector(self) -> list[TenantOwnership]:
        """Materialize the ownerships. Records take precedence over urls."""
        if self.records is None and self.urls is None:
            return []

        if self.records is not None:
            return self.records

        if self.urls is not None:
            return [TenantOwnership.from_str(url) for url in self.urls]

        return []
