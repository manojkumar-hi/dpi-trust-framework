from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.credential import CredentialResponse
from app.services.credential_service import SubjectAgentNotFoundError, get_agent_credentials

router = APIRouter(prefix="/agents", tags=["Verifiable Credentials"])


@router.get(
    "/{agent_id}/credentials",
    response_model=list[CredentialResponse],
    responses={404: {"description": "Agent not found"}},
)
def list_agent_credentials(
    agent_id: UUID, db: Session = Depends(get_db)
) -> list[CredentialResponse]:
    try:
        return get_agent_credentials(db, agent_id)
    except SubjectAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
