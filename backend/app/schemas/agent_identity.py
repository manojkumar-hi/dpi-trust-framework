from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    did: str
    public_key: str
    key_algorithm: str
    status: str
    created_at: datetime
    updated_at: datetime


class VerificationMethod(BaseModel):
    id: str
    type: str
    controller: str
    public_key: str = Field(alias="publicKeyBase64")

    model_config = ConfigDict(populate_by_name=True)


class DIDResolutionResponse(BaseModel):
    context: list[str] = Field(alias="@context")
    id: str
    verification_method: list[VerificationMethod] = Field(alias="verificationMethod")
    authentication: list[str]
    status: str

    model_config = ConfigDict(populate_by_name=True)
