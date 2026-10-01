from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_template_decision import AgentTemplateDecision
from app.schemas.agent import AgentCreate, AgentTemplateRegistrationRequest
from app.schemas.audit import AuditRecordCreate
from app.services.audit_service import AuditService
from app.services.agent_templates.registry import get_template
from app.services.identity_service import create_identity
from app.services.delegation_service import create_delegation
from app.schemas.delegation import DelegationCreate, DelegationCapabilityCreate
from app.api.dependencies import Principal

def create_agent(db: Session, agent_data: AgentCreate) -> Agent:
    agent = Agent(**agent_data.model_dump())
    db.add(agent)
    
    audit_record = AuditRecordCreate(
        event_category="IDENTITY",
        event_type="agent_registered",
        actor_organization_id=agent.organization_id,
        subject_agent_id=agent.id,
        resource_type="agent",
        resource_id=str(agent.id)
    )
    AuditService.create_audit_record(db, audit_record)
    
    db.commit()
    db.refresh(agent)
    return agent


async def register_agent_from_template(
    db: Session, principal: Principal, request: AgentTemplateRegistrationRequest
) -> Agent:
    template = get_template(request.template_id)
    if not template or template.template_version != request.template_version:
        raise HTTPException(status_code=400, detail="Unknown template or unsupported version")

    for cap_code in request.capabilities.keys():
        if cap_code not in template.supported_capabilities:
            raise HTTPException(status_code=400, detail=f"Unsupported capability: {cap_code}")

    # Create agent row
    agent_data = AgentCreate(
        organization_id=request.organization_id,
        name=request.name,
        agent_type=request.template_id,
        description=request.description,
        template_id=request.template_id,
        template_version=request.template_version
    )
    agent = Agent(**agent_data.model_dump())
    db.add(agent)
    db.flush()

    # Save capability decisions
    allowed_caps = []
    for cap_code, decision in request.capabilities.items():
        if decision not in ("ALLOWED", "DENIED"):
            raise HTTPException(status_code=400, detail=f"Invalid decision for {cap_code}")
        
        decision_record = AgentTemplateDecision(
            agent_id=agent.id,
            capability_code=cap_code,
            decision=decision
        )
        db.add(decision_record)
        
        if decision == "ALLOWED":
            allowed_caps.append(cap_code)
            
        AuditService.create_audit_record(db, AuditRecordCreate(
            event_category="SECURITY",
            event_type="capability_decision",
            actor_organization_id=request.organization_id,
            subject_agent_id=agent.id,
            resource_type="capability",
            resource_id=cap_code,
            authorization_decision=decision,
            event_metadata={"template_id": request.template_id}
        ))
    
    db.flush()

    try:
        # Create Identity
        create_identity(db, agent.id)

        # Create Delegation if there are ALLOWED capabilities
        if allowed_caps:
            now = datetime.now(timezone.utc)
            delegation_create = DelegationCreate(
                delegator_organization_id=request.organization_id,
                delegatee_agent_id=agent.id,
                purpose=f"Delegation for {template.display_name}",
                starts_at=now,
                expires_at=now + timedelta(days=365),
                capabilities=[DelegationCapabilityCreate(capability_code=c) for c in allowed_caps]
            )
            await create_delegation(db, principal, delegation_create)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.refresh(agent)
    return agent


def get_agents(db: Session, organization_id: UUID | None = None) -> list[Agent]:
    statement = select(Agent).order_by(Agent.created_at)
    if organization_id is not None:
        statement = statement.where(Agent.organization_id == organization_id)
    return list(db.scalars(statement).all())


def get_agent(db: Session, agent_id: UUID) -> Agent | None:
    return db.get(Agent, agent_id)
