from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, Depends, Request

@dataclass(frozen=True)
class Principal:
    organization_id: UUID
    agent_id: UUID | None = None
    admin_id: UUID | None = None
    subject: str = ""       # The canonical (iss, sub) representation
    scopes: list[str] = field(default_factory=list)

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.connection import get_db, SessionLocal
from app.core.auth import JWTValidator, AuthError
from app.services.audit_service import AuditService
from app.schemas.audit import AuditRecordCreate

security = HTTPBearer(auto_error=False)
jwt_validator = JWTValidator()

def _audit_auth(event_type: str, decision: str, reason_code: str, principal: Principal | None = None):
    with SessionLocal() as db_audit:
        try:
            record = AuditRecordCreate(
                event_category="authentication",
                event_type=event_type,
                actor_did=principal.subject if principal else None,
                actor_organization_id=principal.organization_id if principal else None,
                subject_agent_id=principal.agent_id if principal else None,
                action_requested="authenticate",
                authorization_decision=decision,
                reason_code=reason_code,
            )
            AuditService.create_audit_record(db_audit, record)
            db_audit.commit()
        except Exception:
            db_audit.rollback()
            raise HTTPException(status_code=500, detail="Audit persistence failed")

def get_current_principal(
    request: Request,
    auth_creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
) -> Principal:
    """
    Retrieves the Principal for the current request using JWT authentication.
    """
    if not auth_creds or not auth_creds.credentials:
        _audit_auth("authentication_failed", "DENY", "TOKEN_MISSING")
        raise HTTPException(status_code=401, detail="TOKEN_MISSING")
        
    try:
        claims = jwt_validator.validate_token(auth_creds.credentials)
    except AuthError as e:
        _audit_auth("authentication_failed", "DENY", e.code)
        raise HTTPException(status_code=401, detail=e.code)
        
    from app.services.account_service import is_token_revoked
    jti = claims.get("jti")
    if jti and is_token_revoked(db, jti):
        _audit_auth("authentication_failed", "DENY", "TOKEN_REVOKED")
        raise HTTPException(status_code=401, detail="TOKEN_REVOKED")

    request.state.jwt_claims = claims
    iss = claims["iss"]
    sub = claims["sub"]
    dpi_org_id = claims.get("dpi_org_id")
    dpi_agent_id = claims.get("dpi_agent_id")
    
    if claims.get("dpi_role") == "organization_admin":
        from app.models.organization_administrator import OrganizationAdministrator
        try:
            administrator_id = UUID(claims.get("dpi_admin_id", ""))
            administrator = db.get(OrganizationAdministrator, administrator_id)
        except (TypeError, ValueError):
            administrator = None
        if administrator is None or administrator.status != "active" or str(administrator.organization_id) != dpi_org_id:
            _audit_auth("authentication_failed", "DENY", "IDENTITY_NOT_FOUND")
            raise HTTPException(status_code=401, detail="IDENTITY_NOT_FOUND")
        principal = Principal(
            organization_id=administrator.organization_id,
            admin_id=administrator.id,
            subject=sub,
            scopes=["organization:admin"],
        )
        return principal

    try:
        from app.services.auth_binding_service import resolve_identity_binding
        principal = resolve_identity_binding(
            db=db,
            iss=iss,
            sub=sub,
            dpi_org_id=dpi_org_id,
            dpi_agent_id=dpi_agent_id
        )
    except AuthError as e:
        _audit_auth("authentication_failed", "DENY", e.code)
        raise HTTPException(status_code=401, detail=e.code)
        
    return principal
