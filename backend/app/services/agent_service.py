from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.schemas.agent import AgentCreate


def create_agent(db: Session, agent_data: AgentCreate) -> Agent:
    agent = Agent(**agent_data.model_dump())
    db.add(agent)
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
