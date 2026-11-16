from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.delegation import DelegationResponse
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.organization_service import (
    DuplicateOrganizationDomainError,
    create_organization,
    get_organization,
)
from app.services.delegation_service import get_delegations
from app.api.dependencies import Principal, get_current_principal

router = APIRouter(prefix="/organizations", tags=["Organization Registry"])


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Organization (Bootstrap Operation)",
    description="This is an unauthenticated registry setup operation. In production, this boundary must be restricted at the infrastructure or API-gateway layer."
)
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
def list_organizations(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> list[OrganizationResponse]:
    organization = get_organization(db, principal.organization_id)
    return [organization] if organization is not None else []


@router.get("/{organization_id}", response_model=OrganizationResponse)
def retrieve_organization(
    organization_id: UUID,
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    organization = get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.get("/{organization_id}/delegations", response_model=list[DelegationResponse])
def get_delegations_for_organization(
    organization_id: UUID,
    db: Session = Depends(get_db),
) -> list[DelegationResponse]:
    organization = get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return get_delegations(db, organization_id=organization_id)

