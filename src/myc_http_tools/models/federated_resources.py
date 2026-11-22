from uuid import UUID

from .licensed_resources import LicensedResource


class FederatedResource(LicensedResource):
    """A grant the subject holds on a peer instance.

    Carried apart from the local licensed resources, so a filter never takes a
    foreign grant for a local one unless asked to (``Profile.with_federated``
    or ``Profile.from_issuer``). On the wire it is a licensed resource record
    plus the ``issuer`` member.
    """

    # The instance id of the peer that asserted the grant
    issuer: UUID

    def to_licensed_resource(self) -> LicensedResource:
        """Return the grant without its issuer."""
        return LicensedResource.model_validate(
            self.model_dump(exclude={"issuer"})
        )
