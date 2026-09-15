from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class DelegationCapabilityCreate(BaseModel):
    capability_code: str = Field(..., min_length=1, max_length=100)
    scope: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class DelegationCreate(BaseModel):
    delegator_organization_id: UUID
    delegatee_agent_id: UUID
    purpose: str = Field(..., min_length=1, max_length=1000)
    starts_at: datetime
    expires_at: datetime
    capabilities: list[DelegationCapabilityCreate] = Field(..., min_length=1)
    parent_delegation_id: UUID | None = None


class DelegationCapabilityResponse(DelegationCapabilityCreate):
    model_config = ConfigDict(from_attributes=True)


class DelegationEventResponse(BaseModel):
    id: UUID
    delegation_id: UUID
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    actor_did: str | None = None
    reason: str | None = None
    fabric_transaction_id: str | None = None
    occurred_at: datetime



class DelegationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    delegator_organization_id: UUID
    delegatee_agent_id: UUID
    delegator_did: str
    delegatee_did: str
    parent_delegation_id: UUID | None = None
    root_delegation_id: UUID
    depth: int
    purpose: str
    starts_at: datetime
    expires_at: datetime
    status: str
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    proof_type: str
    verification_method: str
    signing_public_key: str
    signature: str
    signed_at: datetime
    canonical_hash: str
    fabric_transaction_id: str | None = None
    created_at: datetime
    updated_at: datetime
    capabilities: list[DelegationCapabilityResponse]


class RevocationRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class DelegationVerificationResponse(BaseModel):
    delegation_id: UUID
    status: str
    lifecycle_valid: bool
    signature_valid: bool
    hash_valid: bool
    principals_valid: bool
    capabilities_valid: bool
    valid: bool
    verification_message: str