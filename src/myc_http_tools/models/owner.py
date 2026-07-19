from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


def redact_email(email: str) -> str:
    """Mask the local part of an email, keeping the first character and domain.

    Mirrors the mycelium-sdk-js/Go redactEmail helper.
    """
    local, sep, domain = email.partition("@")
    if not sep or not local or not domain:
        return email
    stars = "*" * max(len(local) - 1, 1)
    return f"{local[0]}{stars}@{domain}"


class Owner(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_principal: bool

    def redacted_email(self) -> str:
        """Return the owner email with its local part masked."""
        return redact_email(self.email)
