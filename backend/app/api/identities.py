from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.agent_identity import AgentIdentityResponse
from app.services.identity_service import (
    IdentityAlreadyExistsError,
    create_identity,
    get_agent,
    get_identity_for_agent,
)

router = APIRouter(prefix="/agents", tags=["Agent Identity"])


from app.api.dependencies import Principal, get_current_principal

@router.post(
    "/{agent_id}/identity",
    response_model=AgentIdentityResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Agent not found"},
        409: {"description": "Agent identity already exists"},
    },
)
def create_agent_identity(
    agent_id: UUID = Path(...), 
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal)
) -> AgentIdentityResponse:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if principal.organization_id != agent.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create identity for this agent")
    try:
        return create_identity(db, agent_id)
    except IdentityAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identity already exists for this agent",
        ) from exc


@router.get(
    "/{agent_id}/identity",
    response_model=AgentIdentityResponse,
    responses={404: {"description": "Agent or identity not found"}},
)
def get_agent_identity(
    agent_id: UUID = Path(...), db: Session = Depends(get_db)
) -> AgentIdentityResponse:
    if get_agent(db, agent_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    identity = get_identity_for_agent(db, agent_id)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent identity not found")
    return identity
