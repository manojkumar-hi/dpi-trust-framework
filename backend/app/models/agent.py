from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent_identity import AgentIdentity
    from app.models.delegation import Delegation
    from app.models.organization import Organization
    from app.models.verifiable_credential import VerifiableCredential


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="agents")
    identity: Mapped["AgentIdentity | None"] = relationship(
        back_populates="agent", uselist=False, cascade="all, delete-orphan"
    )
    credentials: Mapped[list["VerifiableCredential"]] = relationship(
        back_populates="subject_agent"
    )
    incoming_delegations: Mapped[list["Delegation"]] = relationship(
        back_populates="delegatee_agent",
        foreign_keys="Delegation.delegatee_agent_id",
    )
