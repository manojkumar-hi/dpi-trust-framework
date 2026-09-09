from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.organization_identity import OrganizationIdentityResponse
from app.services.organization_identity_service import (
    OrganizationIdentityAlreadyExistsError,
    OrganizationNotFoundError,
    create_organization_identity,
    get_organization_identity,
)

router = APIRouter(prefix="/organizations", tags=["Organization Identity"])


@router.post(
    "/{organization_id}/identity",
    response_model=OrganizationIdentityResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Organization not found"},
        409: {"description": "Identity already exists for this organization"},
    },
)
def create_identity(
    organization_id: UUID = Path(...), db: Session = Depends(get_db)
) -> OrganizationIdentityResponse:
    try:
        return create_organization_identity(db, organization_id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from exc
    except OrganizationIdentityAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identity already exists for this organization",
        ) from exc


@router.get(
    "/{organization_id}/identity",
    response_model=OrganizationIdentityResponse,
    responses={404: {"description": "Organization or identity not found"}},
)
def get_identity(
    organization_id: UUID = Path(...), db: Session = Depends(get_db)
) -> OrganizationIdentityResponse:
    try:
        return get_organization_identity(db, organization_id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization identity not found",
        ) from exc
