from uuid import UUID

from pydantic import BaseModel


class OrganizationKeyStatusResponse(BaseModel):
    organization_id: UUID
    did: str
    public_key_available: bool
    private_key_available: bool
    key_algorithm: str