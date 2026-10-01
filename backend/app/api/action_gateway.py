from uuid import UUID
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.action_orchestrator_service import ActionOrchestratorService

router = APIRouter()

class AuthenticationProof(BaseModel):
    type: str = "VerifiablePresentation"
    vp_jwt: str

class ActionRequest(BaseModel):
    challenge_id: UUID
    source_agent_did: str
    target_agent_did: str
    action_type: str
    resource_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    authentication_proof: AuthenticationProof
    delegation_id: UUID | None = None

class ActionResponse(BaseModel):
    execution_id: str
    status: str
    result: dict[str, Any]

@router.post("/gateway/action", response_model=ActionResponse)
async def execute_agent_action(
    request: ActionRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key")
):
    """
    Execute a real agent-to-agent action.
    Authenticates the agent using the provided VP, validates trust against policies,
    executes the operation, and records behavioral evidence.
    """
    result = await ActionOrchestratorService.execute_action(
        db=db,
        challenge_id=request.challenge_id,
        vp_jwt=request.authentication_proof.vp_jwt,
        target_agent_did=request.target_agent_did,
        action_type=request.action_type,
        resource_id=request.resource_id,
        payload=request.payload,
        idempotency_key=idempotency_key,
        delegation_id=request.delegation_id,
        endpoint_path="/api/v1/gateway/action"
    )

    return ActionResponse(
        execution_id=result["execution_id"],
        status=result["status"],
        result=result["result"]
    )
