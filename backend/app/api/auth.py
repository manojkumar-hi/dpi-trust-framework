from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import issuer
from app.database.connection import get_db
from app.services.vp_auth_service import create_challenge, verify_vp_and_consume_challenge, VPAuthError
from app.api import dependencies as auth_dependencies
from app.api.dependencies import Principal, get_current_principal
from app.schemas.account import (
    AdministratorTokenResponse,
    CurrentUserResponse,
    OrganizationRegistrationRequest,
    OrganizationRegistrationResponse,
    PasswordLoginRequest,
)
from app.services.account_service import (
    DuplicateAdministratorError,
    InvalidCredentialsError,
    authenticate_administrator,
    complete_organization_onboarding,
    is_token_revoked,
    issue_administrator_token,
    register_organization,
    revoke_token,
)
from app.models.organization_administrator import OrganizationAdministrator

router = APIRouter(prefix="/auth", tags=["Authentication"])

class ChallengeResponse(BaseModel):
    challenge_id: UUID
    nonce: str
    audience: str
    expires_at: str

class VPLoginRequest(BaseModel):
    challenge_id: UUID
    vp_jwt: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/challenges", response_model=ChallengeResponse)
def generate_challenge(db: Session = Depends(get_db)):
    challenge = create_challenge(db)
    return ChallengeResponse(
        challenge_id=challenge.id,
        nonce=challenge.nonce,
        audience=challenge.audience,
        expires_at=challenge.expires_at.isoformat()
    )

@router.post("/login/vp", response_model=TokenResponse)
def login_with_vp(request: VPLoginRequest, db: Session = Depends(get_db)):
    try:
        agent_identity = verify_vp_and_consume_challenge(
            db=db,
            challenge_id=request.challenge_id,
            vp_jwt=request.vp_jwt
        )

        token = issuer.issue_token(
            subject=agent_identity.did,
            org_id=str(agent_identity.agent.organization_id),
            agent_id=str(agent_identity.agent.id)
        )
        auth_dependencies._audit_auth(
            "authentication_succeeded",
            "ALLOW",
            "AUTHENTICATED",
            Principal(
                organization_id=agent_identity.agent.organization_id,
                agent_id=agent_identity.agent.id,
                subject=agent_identity.did,
            ),
        )
        return TokenResponse(access_token=token)

    except VPAuthError as e:
        raise HTTPException(status_code=401, detail=e.reason_code)


@router.post("/register", response_model=OrganizationRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_account(request: OrganizationRegistrationRequest, db: Session = Depends(get_db)):
    try:
        organization, administrator = register_organization(db, request)
    except DuplicateAdministratorError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    return OrganizationRegistrationResponse(
        organization_id=organization.id,
        administrator_id=administrator.id,
        organization_name=organization.name,
        email=administrator.email,
    )


@router.post("/login", response_model=AdministratorTokenResponse)
def login_with_password(request: PasswordLoginRequest, db: Session = Depends(get_db)):
    try:
        organization, administrator = authenticate_administrator(db, request.email, request.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = issue_administrator_token(organization, administrator)
    auth_dependencies._audit_auth(
        "authentication_succeeded",
        "ALLOW",
        "AUTHENTICATED",
        Principal(
            organization_id=organization.id,
            admin_id=administrator.id,
            subject=administrator.email,
            scopes=["organization:admin"],
        ),
    )
    return AdministratorTokenResponse(
        access_token=token,
        onboarding_completed=organization.onboarding_completed,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(get_current_principal)):
    claims = getattr(request.state, "jwt_claims", None)
    if claims and claims.get("jti"):
        revoke_token(db, claims["jti"], datetime.fromtimestamp(claims["exp"], tz=timezone.utc))


@router.get("/me", response_model=CurrentUserResponse)
def current_user(db: Session = Depends(get_db), principal: Principal = Depends(get_current_principal)):
    if principal.admin_id is None:
        raise HTTPException(status_code=403, detail="Organization administrator account required")
    administrator = db.get(OrganizationAdministrator, principal.admin_id)
    if administrator is None or administrator.status != "active":
        raise HTTPException(status_code=401, detail="Administrator account is not active")
    return CurrentUserResponse(
        administrator_id=administrator.id,
        organization_id=administrator.organization_id,
        organization_name=administrator.organization.name,
        full_name=administrator.full_name,
        email=administrator.email,
        phone=administrator.phone,
        role="organization_admin",
        onboarding_completed=administrator.organization.onboarding_completed,
    )


@router.post("/onboarding/complete", response_model=CurrentUserResponse)
def complete_onboarding(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
):
    if principal.admin_id is None:
        raise HTTPException(status_code=403, detail="Organization administrator account required")
    administrator = db.get(OrganizationAdministrator, principal.admin_id)
    if administrator is None or administrator.status != "active":
        raise HTTPException(status_code=401, detail="Administrator account is not active")
    complete_organization_onboarding(db, administrator.organization)
    return CurrentUserResponse(
        administrator_id=administrator.id,
        organization_id=administrator.organization_id,
        organization_name=administrator.organization.name,
        full_name=administrator.full_name,
        email=administrator.email,
        phone=administrator.phone,
        role="organization_admin",
        onboarding_completed=administrator.organization.onboarding_completed,
    )


class DevLoginRequest(BaseModel):
    organization_id: UUID
    agent_id: UUID

@router.post("/login/dev", response_model=TokenResponse)
def login_dev(request: DevLoginRequest, db: Session = Depends(get_db)):
    """
    LOCAL DEMO BOOTSTRAP: Do not use in production. 
    This allows UI bootstrapping without a wallet for Review-2 demo.
    """
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.auth_dev_login_enabled:
        raise HTTPException(status_code=404, detail="Not Found")

    from app.services.organization_service import get_organization
    org = get_organization(db, request.organization_id)
    if not org:
        raise HTTPException(status_code=400, detail="Invalid organization")

    from app.services.agent_service import get_agent
    agent = get_agent(db, request.agent_id)
    if not agent:
        raise HTTPException(status_code=400, detail="Invalid agent")

    if agent.organization_id != org.id:
        raise HTTPException(status_code=400, detail="Agent does not belong to organization")

    if not agent.identity:
        raise HTTPException(status_code=400, detail="Agent has no established identity")

    token = issuer.issue_token(
        subject=agent.identity.authentication_subject or agent.identity.did,
        org_id=str(org.id),
        agent_id=str(agent.id)
    )
    auth_dependencies._audit_auth(
        "authentication_succeeded",
        "ALLOW",
        "AUTHENTICATED",
        Principal(organization_id=org.id, agent_id=agent.id, subject=agent.identity.authentication_subject or agent.identity.did),
    )
    return TokenResponse(access_token=token)
