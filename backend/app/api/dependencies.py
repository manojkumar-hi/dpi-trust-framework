from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Header, HTTPException

@dataclass(frozen=True)
class Principal:
    organization_id: UUID
    # Future OIDC fields can be added here (e.g. subject, roles)


def get_current_principal(
    x_mock_principal_org_id: str | None = Header(None, alias="X-Mock-Principal-Org-Id")
) -> Principal:
    """
    Development/Test boundary for authentication.
    In Phase 6+, this will decode a JWT or OIDC token.
    For Phase 5, we use a test header specifically intended for local testing,
    ensuring it is fully decoupled from the core service logic.
    """
    if not x_mock_principal_org_id:
        raise HTTPException(status_code=401, detail="Unauthenticated: Principal required")
    try:
        org_id = UUID(x_mock_principal_org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Principal UUID format")
    
    return Principal(organization_id=org_id)
