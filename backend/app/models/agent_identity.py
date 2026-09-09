from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent


class AgentIdentity(Base):
    __tablename__ = "agent_identities"
    __table_args__ = (UniqueConstraint("agent_id", name="uq_agent_identities_agent_id"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    did: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_algorithm: Mapped[str] = mapped_column(String(100), nullable=False, default="Ed25519")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    agent: Mapped["Agent"] = relationship(back_populates="identity")
