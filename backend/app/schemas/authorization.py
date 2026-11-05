from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field

class AuthorizationDecision(BaseModel):
    is_allowed: bool
    reason_code: str
    explanation: str
    evidence: Dict[str, Any]


class AuthorizationPreCheckRequest(BaseModel):
    agent_id: UUID
    action_type: str = Field(min_length=1, max_length=100)
    delegation_id: UUID | None = None


class AuthorizationPreCheckResponse(AuthorizationDecision):
    agent_id: UUID
    action_type: str
    resource_type: str
