from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    organization_id: UUID
    name: str = Field(..., max_length=255)
    agent_type: str = Field(..., max_length=100)
    description: str | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    agent_type: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
