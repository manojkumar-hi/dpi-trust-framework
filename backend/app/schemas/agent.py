from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentTemplateToolSchema(BaseModel):
    name: str
    description: str
    capability_code: str


class AgentTemplateSchema(BaseModel):
    template_id: str
    template_version: str
    display_name: str
    description: str
    system_prompt: str
    tools: list[AgentTemplateToolSchema]


class AgentCreate(BaseModel):
    organization_id: UUID
    name: str = Field(..., max_length=255)
    agent_type: str = Field(..., max_length=100)
    description: str | None = None
    template_id: str | None = Field(default=None, max_length=255)
    template_version: str | None = Field(default=None, max_length=50)


class AgentTemplateRegistrationRequest(BaseModel):
    organization_id: UUID
    name: str = Field(..., max_length=255)
    description: str | None = None
    template_id: str = Field(..., max_length=255)
    template_version: str = Field(..., max_length=50)
    capabilities: dict[str, str] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    agent_type: str
    description: str | None
    template_id: str | None
    template_version: str | None
    status: str
    created_at: datetime
    updated_at: datetime
