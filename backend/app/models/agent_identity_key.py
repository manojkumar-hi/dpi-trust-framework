from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent_identity import AgentIdentity


class AgentIdentityKey(Base):
    __tablename__ = "agent_identity_keys"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'retired')",
            name="ck_agent_identity_keys_valid_status",
        ),
        Index(
            "uq_agent_identity_keys_active",
            "agent_identity_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_identity_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("agent_identities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_method: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_algorithm: Mapped[str] = mapped_column(String(100), nullable=False, default="Ed25519")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent_identity: Mapped["AgentIdentity"] = relationship(back_populates="keys")
