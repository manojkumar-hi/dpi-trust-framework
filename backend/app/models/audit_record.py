from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, func, Index
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (
        Index("ix_audit_records_correlation_id", "correlation_id"),
        Index("ix_audit_records_category_type", "event_category", "event_type"),
        Index("ix_audit_records_occurred_at", "occurred_at"),
        Index("ix_audit_records_actor_organization", "actor_organization_id"),
        Index("ix_audit_records_subject_agent", "subject_agent_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    correlation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_category: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(default=1, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    actor_did: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_organization_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    subject_agent_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_requested: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    authorization_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    trust_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evidence_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
