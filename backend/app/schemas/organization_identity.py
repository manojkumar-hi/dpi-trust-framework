from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrganizationIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    did: str
    public_key: str
    key_algorithm: str
    status: str
    created_at: datetime
    updated_at: datetime
