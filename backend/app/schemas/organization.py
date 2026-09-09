from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., max_length=255)
    domain: str = Field(..., max_length=255)
    description: str | None = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
