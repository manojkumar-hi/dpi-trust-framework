from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.organization_identity import OrganizationIdentityResponse
from app.schemas.organization_key import OrganizationKeyStatusResponse
from app.services.organization_identity_service import (
    OrganizationNotFoundError,
    get_organization,
    get_organization_identity,
    rekey_organization_identity,
)
from app.services.organization_key_service import private_key_path

router = APIRouter(prefix="/organizations", tags=["Organization Key Management"])


@router.post(
    "/{organization_id}/identity/rekey",
    response_model=OrganizationIdentityResponse,
    responses={404: {"description": "Organization or identity not found"}},
)
def rekey_identity(
    organization_id: UUID = Path(...), db: Session = Depends(get_db)
) -> OrganizationIdentityResponse:
    try:
        return rekey_organization_identity(db, organization_id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Organization not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Organization identity not found") from exc


@router.get(
    "/{organization_id}/identity/key-status",
    response_model=OrganizationKeyStatusResponse,
    responses={404: {"description": "Organization or identity not found"}},
)
def identity_key_status(
    organization_id: UUID = Path(...), db: Session = Depends(get_db)
) -> OrganizationKeyStatusResponse:
    if get_organization(db, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    try:
        identity = get_organization_identity(db, organization_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Organization identity not found") from exc
    return OrganizationKeyStatusResponse(
        organization_id=organization_id,
        did=identity.did,
        public_key_available=bool(identity.public_key),
        private_key_available=private_key_path(organization_id).is_file(),
        key_algorithm=identity.key_algorithm,
    )
