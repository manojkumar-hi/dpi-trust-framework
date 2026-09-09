from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.agent import AgentCreate, AgentResponse
from app.services.agent_service import create_agent, get_agent, get_agents
from app.services.organization_service import get_organization

router = APIRouter(prefix="/agents", tags=["Agent Registry"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent_endpoint(agent_data: AgentCreate, db: Session = Depends(get_db)) -> AgentResponse:
    if get_organization(db, agent_data.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return create_agent(db, agent_data)


@router.get("", response_model=list[AgentResponse])
def list_agents(
    organization_id: UUID | None = Query(default=None), db: Session = Depends(get_db)
) -> list[AgentResponse]:
    return get_agents(db, organization_id)


@router.get("/{agent_id}", response_model=AgentResponse)
def retrieve_agent(agent_id: UUID, db: Session = Depends(get_db)) -> AgentResponse:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent
