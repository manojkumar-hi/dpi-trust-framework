from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.audit import AuditRecordResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.get("", response_model=list[AuditRecordResponse])
def get_audit_logs(
    correlation_id: str | None = Query(default=None),
    subject_agent_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AuditRecordResponse]:
    """
    Read-only endpoint to retrieve audit records.
    Pagination is deterministic.
    """
    return AuditService.get_audit_records(
        db,
        correlation_id=correlation_id,
        subject_agent_id=subject_agent_id,
        limit=limit,
        offset=offset
    )
