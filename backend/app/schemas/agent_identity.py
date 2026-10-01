from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentIdentityCreateRequest(BaseModel):
    public_key_b64: str | None = Field(
        None, 
        description="Base64 encoded raw Ed25519 public key. If provided, the framework will use this key (BYOK). If omitted, the framework will generate a key for backwards compatibility."
    )

class AgentIdentityRekeyRequest(BaseModel):
    public_key_b64: str | None = Field(
        None, 
        description="Base64 encoded raw Ed25519 public key. If provided, the framework will use this key (BYOK). If omitted, the framework will generate a key for backwards compatibility."
    )

class AgentIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    did: str
    public_key: str | None = None
    key_algorithm: str | None = None
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
    assertion_method: list[str] = Field(alias="assertionMethod", default_factory=list)
    status: str

    model_config = ConfigDict(populate_by_name=True)
