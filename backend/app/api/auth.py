from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import issuer
from app.database.connection import get_db
from app.services.vp_auth_service import create_challenge, verify_vp_and_consume_challenge, VPAuthError

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
        return TokenResponse(access_token=token)

    except VPAuthError as e:
        raise HTTPException(status_code=401, detail=e.reason_code)


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
    return TokenResponse(access_token=token)
