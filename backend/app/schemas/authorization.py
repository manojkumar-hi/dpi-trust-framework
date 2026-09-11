from typing import Any, Dict
from pydantic import BaseModel

class AuthorizationDecision(BaseModel):
    is_allowed: bool
    reason_code: str
    explanation: str
    evidence: Dict[str, Any]
