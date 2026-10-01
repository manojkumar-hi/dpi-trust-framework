from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.behavioral_evidence import BehavioralEvidence


class AgentActionLog(Base):
    __tablename__ = "agent_action_logs"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    execution_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    source_agent_did: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_agent_did: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_agent_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    target_agent_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # SUCCESS, DENIED, FAILED, PENDING
    payload_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    evidence: Mapped["BehavioralEvidence"] = relationship(back_populates="action_log", uselist=False)
