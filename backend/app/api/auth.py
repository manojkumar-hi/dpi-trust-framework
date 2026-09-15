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
