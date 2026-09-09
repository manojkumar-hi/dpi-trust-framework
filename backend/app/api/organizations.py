from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.organization_service import (
    DuplicateOrganizationDomainError,
    create_organization,
    get_organization,
    get_organizations,
)

router = APIRouter(prefix="/organizations", tags=["Organization Registry"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization_endpoint(
    organization_data: OrganizationCreate, db: Session = Depends(get_db)
) -> OrganizationResponse:
    try:
        return create_organization(db, organization_data)
    except DuplicateOrganizationDomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this domain already exists",
        ) from exc


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(db: Session = Depends(get_db)) -> list[OrganizationResponse]:
    return get_organizations(db)


@router.get("/{organization_id}", response_model=OrganizationResponse)
def retrieve_organization(
    organization_id: UUID, db: Session = Depends(get_db)
) -> OrganizationResponse:
    organization = get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization
