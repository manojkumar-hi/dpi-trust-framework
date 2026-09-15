from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from app.database.base import Base


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    organization_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False)
    endpoint_path = Column(String(255), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)  # SHA-256 hash length is 64 hex chars
    response_body = Column(JSONB, nullable=True)
    response_status_code = Column(String(10), nullable=True)  # Store as string or int
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_idempotency_org_key"),
    )
