from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent


class AgentTrustState(Base):
    __tablename__ = "agent_trust_state"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, unique=True
    )
    positive_evidence_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    negative_evidence_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_window_r: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    agent: Mapped["Agent"] = relationship(backref="trust_state")
