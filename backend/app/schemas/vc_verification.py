from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VCVerifyRequest(BaseModel):
    vc_jwt: str = Field(..., description="The compact serialised W3C vc+jwt string to verify")


class VCVerificationResult(BaseModel):
    valid: bool
    reason_code: str

    issuer_did: str | None = None
    subject_did: str | None = None
    credential_type: str | None = None
    jti: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None

    kid: str | None = None
    signature_status: str
    proof_type: str = "EdDSAvc+jwt"

    vc_context: list[str] | None = None
    vc_type: list[str] | None = None
    credential_subject: dict[str, Any] | None = None

    local_credential_id: UUID | None = None
    local_status: str | None = None
    fabric_transaction_id: str | None = None

    message: str
