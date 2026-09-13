from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class AuditRecordCreate(BaseModel):
    correlation_id: Optional[str] = None
    event_category: str = Field(..., max_length=50)
    event_type: str = Field(..., max_length=100)
    actor_did: Optional[str] = Field(None, max_length=500)
    actor_organization_id: Optional[UUID] = None
    subject_agent_id: Optional[UUID] = None
    resource_type: Optional[str] = Field(None, max_length=100)
    resource_id: Optional[str] = Field(None, max_length=255)
    action_requested: Optional[str] = Field(None, max_length=100)
    authorization_decision: Optional[str] = Field(None, max_length=50)
    reason_code: Optional[str] = Field(None, max_length=100)
    policy_id: Optional[str] = Field(None, max_length=100)
    trust_snapshot: Optional[dict[str, Any]] = None
    evidence_snapshot: Optional[dict[str, Any]] = None
    event_metadata: Optional[dict[str, Any]] = None

class AuditRecordResponse(AuditRecordCreate):
    id: UUID
    event_version: int
    occurred_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
