from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.schemas.agent import AgentCreate
from app.schemas.audit import AuditRecordCreate
from app.services.audit_service import AuditService

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


def get_agents(db: Session, organization_id: UUID | None = None) -> list[Agent]:
    statement = select(Agent).order_by(Agent.created_at)
    if organization_id is not None:
        statement = statement.where(Agent.organization_id == organization_id)
    return list(db.scalars(statement).all())


def get_agent(db: Session, agent_id: UUID) -> Agent | None:
    return db.get(Agent, agent_id)
