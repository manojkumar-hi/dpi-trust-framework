import copy
from typing import Any, Dict
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_record import AuditRecord
from app.schemas.audit import AuditRecordCreate
from app.core.correlation import get_correlation_id

SENSITIVE_KEYS = {
    "private_key",
    "password",
    "secret",
    "token",
    "authorization",
    "access_token",
    "signature",
    "signing_public_key"
}

def _strip_sensitive_data(data: Any) -> Any:
    if isinstance(data, dict):
        clean_dict = {}
        for k, v in data.items():
            if k.lower() in SENSITIVE_KEYS:
                clean_dict[k] = "[REDACTED]"
            else:
                clean_dict[k] = _strip_sensitive_data(v)
        return clean_dict
    elif isinstance(data, list):
        return [_strip_sensitive_data(item) for item in data]
    else:
        return data

class AuditService:
    @staticmethod
    def create_audit_record(db: Session, record_in: AuditRecordCreate) -> AuditRecord:
        # Strip sensitive data before persisting
        safe_trust_snapshot = _strip_sensitive_data(record_in.trust_snapshot) if record_in.trust_snapshot else None
        safe_evidence_snapshot = _strip_sensitive_data(record_in.evidence_snapshot) if record_in.evidence_snapshot else None
        safe_event_metadata = _strip_sensitive_data(record_in.event_metadata) if record_in.event_metadata else None
        
        # Inject context-local correlation ID if not explicitly provided
        correlation_id = record_in.correlation_id or get_correlation_id()

        record = AuditRecord(
            correlation_id=correlation_id,
            event_category=record_in.event_category,
            event_type=record_in.event_type,
            actor_did=record_in.actor_did,
            actor_organization_id=record_in.actor_organization_id,
            subject_agent_id=record_in.subject_agent_id,
            resource_type=record_in.resource_type,
            resource_id=record_in.resource_id,
            action_requested=record_in.action_requested,
            authorization_decision=record_in.authorization_decision,
            reason_code=record_in.reason_code,
            policy_id=record_in.policy_id,
            trust_snapshot=safe_trust_snapshot,
            evidence_snapshot=safe_evidence_snapshot,
            event_metadata=safe_event_metadata,
        )
        db.add(record)
        # We do NOT commit here. The caller decides the transaction boundary.
        # This allows auth failures to commit, and resource success to share the resource commit.
        db.flush()
        return record

    @staticmethod
    def get_audit_records(
        db: Session,
        correlation_id: str | None = None,
        subject_agent_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditRecord]:
        query = select(AuditRecord).order_by(AuditRecord.occurred_at.desc())
        
        if correlation_id:
            query = query.where(AuditRecord.correlation_id == correlation_id)
        if subject_agent_id:
            query = query.where(AuditRecord.subject_agent_id == subject_agent_id)
            
        query = query.limit(limit).offset(offset)
        return list(db.scalars(query).all())
