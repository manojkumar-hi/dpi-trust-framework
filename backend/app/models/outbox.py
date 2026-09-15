from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

from app.database.base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, index=True)
    event_type = Column(String(255), nullable=False)
    aggregate_id = Column(String(36), nullable=False, index=True)
    payload = Column(JSONB, nullable=False)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String, nullable=True)
    fabric_transaction_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
