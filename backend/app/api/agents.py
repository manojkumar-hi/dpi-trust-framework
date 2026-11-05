from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.agent import AgentCreate, AgentResponse, AgentTemplateRegistrationRequest
from app.schemas.delegation import DelegationResponse

from app.services.agent_service import create_agent, get_agent, get_agents, register_agent_from_template
from app.services.agent_templates.registry import list_templates
from app.services.delegation_service import get_delegations
from app.services.organization_service import get_organization
from app.api.dependencies import Principal, get_current_principal
from app.schemas.agent import AgentTemplateSchema
from app.models.agent_action_log import AgentActionLog

from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/agents", tags=["Agent Registry"])


class AgentActionHistoryItem(BaseModel):
    execution_id: str
    action_type: str
    status: str
    timestamp: datetime


@router.get("/{agent_id}/actions", response_model=list[AgentActionHistoryItem])
def get_agent_action_history(
    agent_id: UUID,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[AgentActionHistoryItem]:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if principal.organization_id != agent.organization_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this agent's action history")
    records = db.scalars(
        select(AgentActionLog)
        .where(AgentActionLog.source_agent_id == agent_id)
        .order_by(AgentActionLog.timestamp.desc())
        .limit(limit)
    ).all()
    return [AgentActionHistoryItem.model_validate(record, from_attributes=True) for record in records]

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent_endpoint(
    agent_data: AgentCreate, 
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal)
) -> AgentResponse:
    if principal.organization_id != agent_data.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create agents for this organization")
    if get_organization(db, agent_data.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return create_agent(db, agent_data)


@router.get("/templates", response_model=list[AgentTemplateSchema])
def list_agent_templates() -> list[AgentTemplateSchema]:
    templates = list_templates()
    return [
        AgentTemplateSchema(
            template_id=t.template_id,
            template_version=t.template_version,
            display_name=t.display_name,
            description=t.description,
            system_prompt=t.system_prompt,
            tools=[{"name": tool.name, "description": tool.description, "capability_code": tool.capability_code} for tool in t.tools]
        )
        for t in templates
    ]



@router.post("/register-template", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_template_endpoint(
    request: AgentTemplateRegistrationRequest, 
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal)
) -> AgentResponse:
    if principal.organization_id != request.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create agents for this organization")
    if get_organization(db, request.organization_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return await register_agent_from_template(db, principal, request)


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


@router.get("/{agent_id}/delegations", response_model=list[DelegationResponse])
def get_delegations_for_agent(agent_id: UUID, db: Session = Depends(get_db)) -> list[DelegationResponse]:
    agent = get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return get_delegations(db, agent_id=agent_id)

from app.api.dependencies import Principal, get_current_principal
from app.api.authorization_dependency import authorize_action
from pydantic import BaseModel

class SensitiveOpResponse(BaseModel):
    message: str
    decision: dict

@router.post("/{agent_id}/simulated-sensitive-op", response_model=SensitiveOpResponse)
async def simulated_sensitive_op(
    agent_id: UUID,
    delegation_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal)
):
    # This policy rule requires:
    # requires_delegation=True, required_capability="dpi.auth.issue"
    # required_trust=0.8, max_recent_risk=0.1, max_uncertainty=0.2
    decision = await authorize_action(
        resource_type="verifiable_credential",
        action_name="issue",
        db=db,
        principal=principal,
        agent_id=agent_id,
        delegation_id=delegation_id
    )
    return SensitiveOpResponse(
        message="Simulated sensitive operation executed successfully.",
        decision={"reason_code": decision.reason_code, "explanation": decision.explanation}
    )
