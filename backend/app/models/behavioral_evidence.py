from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent


class BehavioralEvidence(Base):
    __tablename__ = "behavioral_evidence"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)  # 'success' or 'failure'
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True) # 1,2,4,8,16
    evidence_quality: Mapped[float] = mapped_column(Float, nullable=False) # 0 <= Q <= 1
    informative_value: Mapped[float | None] = mapped_column(Float, nullable=True) # (0, 1]
    action_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent: Mapped["Agent"] = relationship(backref="behavioral_evidence")
