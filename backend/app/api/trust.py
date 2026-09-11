from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import Principal, get_current_principal
from app.database.connection import get_db
from app.schemas.trust import EvidenceIngestionRequest, EvidenceIngestionResponse, TrustScoreResponse
from app.services.trust_service import TrustService

router = APIRouter(prefix="/agents", tags=["trust"])


@router.get("/{id}/trust", response_model=TrustScoreResponse)
def get_trust_score(
    id: UUID,
    db: Session = Depends(get_db),
):
    return TrustService.get_trust_score(db, agent_id=id)


@router.post(
    "/{id}/trust/evidence",
    response_model=EvidenceIngestionResponse,
    status_code=201,
)
def ingest_evidence(
    id: UUID,
    request: EvidenceIngestionRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    evidence = TrustService.ingest_evidence(
        db, agent_id=id, request=request, principal_org_id=principal.organization_id
    )
    
    return EvidenceIngestionResponse(
        id=evidence.id,
        agent_id=evidence.agent_id,
        timestamp=evidence.timestamp,
        outcome=evidence.outcome,
        severity=evidence.severity,
        evidence_quality=evidence.evidence_quality,
        informative_value=evidence.informative_value,
        action_metadata=evidence.action_metadata,
    )
