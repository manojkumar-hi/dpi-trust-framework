from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent

class AgentTemplateDecision(Base):
    __tablename__ = "agent_template_decisions"
    __table_args__ = (
        UniqueConstraint("agent_id", "capability_code", name="uq_agent_template_decision"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "ALLOWED", "DENIED"
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    agent: Mapped["Agent"] = relationship(back_populates="template_decisions")
