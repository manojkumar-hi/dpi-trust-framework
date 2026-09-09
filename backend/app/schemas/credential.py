from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CredentialCreate(BaseModel):
    issuer_organization_id: UUID
    subject_agent_id: UUID
    credential_type: str = Field(..., max_length=150)
    credential_data: dict[str, Any]
    expires_at: datetime | None = None


class CredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    issuer_organization_id: UUID
    subject_agent_id: UUID
    credential_type: str
    credential_data: dict[str, Any]
    status: str
    issued_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    revocation_reason: str | None
    proof_type: str | None
    signature: str | None
    signed_at: datetime | None
    transaction_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CredentialRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class CredentialVerificationResponse(BaseModel):
    credential_id: UUID
    credential_type: str
    issuer_did: str | None
    subject_did: str | None
    status: str
    lifecycle_valid: bool
    cryptographically_verified: bool
    signature_status: str
    proof_type: str | None
    valid: bool
    issued_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    verification_message: str
