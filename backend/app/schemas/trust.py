from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EvidenceIngestionRequest(BaseModel):
    outcome: str = Field(..., description="Must be 'success' or 'failure'")
    severity: int | None = Field(None, description="Must be 1, 2, 4, 8, or 16 for failures")
    evidence_quality: float = Field(..., ge=0.0, le=1.0, description="Evidence quality [0, 1]")
    informative_value: float | None = Field(None, gt=0.0, le=1.0, description="Informative value (0, 1] for successes")
    action_metadata: dict[str, Any] | None = Field(None, description="Metadata about the action")

    @model_validator(mode="after")
    def validate_outcome_fields(self):
        if self.outcome == "success":
            if self.severity is not None:
                raise ValueError("severity must be null for success outcomes")
            if self.informative_value is None:
                raise ValueError("informative_value is required for success outcomes")
        elif self.outcome == "failure":
            if self.severity not in (1, 2, 4, 8, 16):
                raise ValueError("severity must be one of: 1, 2, 4, 8, 16 for failure outcomes")
            if self.informative_value is not None:
                raise ValueError("informative_value must be null for failure outcomes")
        else:
            raise ValueError("outcome must be 'success' or 'failure'")
        return self


class EvidenceIngestionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    timestamp: datetime
    outcome: str
    severity: int | None
    evidence_quality: float
    informative_value: float | None
    action_metadata: dict[str, Any] | None


class TrustScoreResponse(BaseModel):
    agent_id: UUID
    trust: float
    belief: float
    disbelief: float
    uncertainty: float
    recent_risk: float
    positive_evidence: float
    negative_evidence: float
