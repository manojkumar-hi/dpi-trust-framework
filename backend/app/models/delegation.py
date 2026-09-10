from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.delegation_capability import DelegationCapability
    from app.models.delegation_event import DelegationEvent
    from app.models.organization import Organization


class Delegation(Base):
    __tablename__ = "delegations"
    __table_args__ = (
        CheckConstraint("starts_at < expires_at", name="ck_delegations_start_before_expiry"),
        CheckConstraint("depth >= 0", name="ck_delegations_non_negative_depth"),
        CheckConstraint(
            "status IN ('active', 'revoked', 'expired')",
            name="ck_delegations_valid_status",
        ),
        CheckConstraint(
            "(status = 'revoked' AND revoked_at IS NOT NULL AND revocation_reason IS NOT NULL AND length(trim(revocation_reason)) > 0) OR (status <> 'revoked' AND revoked_at IS NULL)",
            name="ck_delegations_revocation_fields",
        ),
        Index("ix_delegations_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    delegator_organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    delegatee_agent_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    delegator_did: Mapped[str] = mapped_column(String(500), nullable=False)
    delegatee_did: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_delegation_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("delegations.id"), nullable=True, index=True
    )
    root_delegation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("delegations.id"), nullable=False, index=True
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_type: Mapped[str] = mapped_column(String(100), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(500), nullable=False)
    signing_public_key: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    fabric_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    delegator_organization: Mapped["Organization"] = relationship(
        back_populates="outgoing_delegations", foreign_keys=[delegator_organization_id]
    )
    delegatee_agent: Mapped["Agent"] = relationship(
        back_populates="incoming_delegations", foreign_keys=[delegatee_agent_id]
    )
    parent: Mapped["Delegation | None"] = relationship(
        back_populates="children", remote_side=[id], foreign_keys=[parent_delegation_id]
    )
    children: Mapped[list["Delegation"]] = relationship(
        back_populates="parent", foreign_keys=[parent_delegation_id]
    )
    capabilities: Mapped[list["DelegationCapability"]] = relationship(
        back_populates="delegation", cascade="all, delete-orphan"
    )
    events: Mapped[list["DelegationEvent"]] = relationship(
        back_populates="delegation", cascade="all, delete-orphan", order_by="DelegationEvent.occurred_at"
    )