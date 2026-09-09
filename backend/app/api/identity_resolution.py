from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.agent_identity import DIDResolutionResponse
from app.services.identity_service import resolve_did

router = APIRouter(prefix="/identities", tags=["DID Resolution"])


@router.get(
    "/resolve/{did}",
    response_model=DIDResolutionResponse,
    response_model_by_alias=True,
    responses={404: {"description": "DID not found"}},
)
def resolve_identity(
    did: str = Path(..., min_length=9, max_length=500), db: Session = Depends(get_db)
) -> DIDResolutionResponse:
    identity = resolve_did(db, did)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DID not found")
    return identity
