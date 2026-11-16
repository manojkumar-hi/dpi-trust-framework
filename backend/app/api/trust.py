from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import Principal, get_current_principal
from app.database.connection import get_db
from app.schemas.trust import EvidenceIngestionRequest, EvidenceIngestionResponse, TrustScoreResponse
from app.services.trust_service import TrustService
from app.services.agent_service import get_agent

router = APIRouter(prefix="/agents", tags=["trust"])


@router.get("/{id}/trust", response_model=TrustScoreResponse)
def get_trust_score(
    id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    agent = get_agent(db, id)
    if agent is None or agent.organization_id != principal.organization_id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return TrustService.get_trust_score(db, agent_id=id)


from app.services.idempotency_service import IdempotencyService
from fastapi import Header

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
    idempotency_key: str | None = Header(None, alias="Idempotency-Key")
):
    if idempotency_key:
        cached = IdempotencyService.check_and_lock_idempotency(
            db, 
            principal.organization_id, 
            idempotency_key, 
            f"/agents/{id}/trust/evidence", 
            request.model_dump(mode="json")
        )
        if cached:
            return EvidenceIngestionResponse(**cached)

    evidence = TrustService.ingest_evidence(
        db, agent_id=id, request=request, principal_org_id=principal.organization_id
    )
    
    response = EvidenceIngestionResponse(
        id=evidence.id,
        agent_id=evidence.agent_id,
        timestamp=evidence.timestamp,
        outcome=evidence.outcome,
        severity=evidence.severity,
        evidence_quality=evidence.evidence_quality,
        informative_value=evidence.informative_value,
        action_metadata=evidence.action_metadata,
    )

    if idempotency_key:
        IdempotencyService.update_idempotency_response(
            db, 
            principal.organization_id, 
            idempotency_key, 
            response.model_dump(mode="json"), 
            201
        )
    
    db.commit()
    return response
