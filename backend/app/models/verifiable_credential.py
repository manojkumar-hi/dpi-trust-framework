from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.organization import Organization
    from app.models.bitstring_status_list import BitstringStatusList


class VerifiableCredential(Base):
    __tablename__ = "verifiable_credentials"
    __table_args__ = (
        Index("ix_verifiable_credentials_issuer_organization_id", "issuer_organization_id"),
        Index("ix_verifiable_credentials_subject_agent_id", "subject_agent_id"),
        Index("ix_verifiable_credentials_credential_type", "credential_type"),
        Index("ix_verifiable_credentials_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    issuer_organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    subject_agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    credential_type: Mapped[str] = mapped_column(String(150), nullable=False)
    credential_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vc_jwt: Mapped[str | None] = mapped_column(Text, nullable=True)
    kid: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_list_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("bitstring_status_lists.id"), nullable=True, index=True
    )
    status_list_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    issuer_organization: Mapped["Organization"] = relationship(back_populates="issued_credentials")
    subject_agent: Mapped["Agent"] = relationship(back_populates="credentials")
