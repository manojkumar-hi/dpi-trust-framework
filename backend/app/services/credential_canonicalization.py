import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def canonical_credential_bytes(
    credential_id: UUID,
    issuer_organization_id: UUID,
    subject_agent_id: UUID,
    credential_type: str,
    credential_data: dict[str, Any],
    issued_at: datetime,
    expires_at: datetime | None,
) -> bytes:
    data = {
        "credential_data": credential_data,
        "credential_id": str(credential_id),
        "credential_type": credential_type,
        "expires_at": _timestamp(expires_at),
        "issued_at": _timestamp(issued_at),
        "issuer_organization_id": str(issuer_organization_id),
        "subject_agent_id": str(subject_agent_id),
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def credential_hash(
    credential_id: UUID,
    issuer_organization_id: UUID,
    subject_agent_id: UUID,
    credential_type: str,
    credential_data: dict[str, Any],
    issued_at: datetime,
    expires_at: datetime | None,
) -> str:
    canonical_bytes = canonical_credential_bytes(
        credential_id,
        issuer_organization_id,
        subject_agent_id,
        credential_type,
        credential_data,
        issued_at,
        expires_at,
    )
    return hashlib.sha256(canonical_bytes).hexdigest()
