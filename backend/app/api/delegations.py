from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import Principal, get_current_principal
from app.database.connection import get_db
from app.schemas.delegation import (
    DelegationCreate,
    DelegationResponse,
    DelegationVerificationResponse,
    RevocationRequest,
)
from app.services.delegation_service import (
    AuthorizationError,
    DelegationAlreadyRevokedError,
    DelegationNotFoundError,
    InvalidDelegationError,
    OrganizationSigningKeyUnavailableError,
    create_delegation,
    get_delegation,
    get_delegation_chain,
    get_delegations,
    revoke_delegation,
    verify_delegation,
)

router = APIRouter(prefix="/delegations", tags=["Delegation Management"])


@router.post("", response_model=DelegationResponse, status_code=status.HTTP_201_CREATED)
async def create_delegation_endpoint(
    delegation_data: DelegationCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> DelegationResponse:
    try:
        return await create_delegation(db, principal, delegation_data)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except InvalidDelegationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except OrganizationSigningKeyUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization signing key unavailable",
        )


@router.get("", response_model=list[DelegationResponse])
def list_delegations(
    db: Session = Depends(get_db),
    principal: dict = Depends(get_current_principal),
) -> list[DelegationResponse]:
    return get_delegations(db)


@router.get("/{delegation_id}", response_model=DelegationResponse)
def retrieve_delegation(
    delegation_id: UUID,
    db: Session = Depends(get_db),
    principal: dict = Depends(get_current_principal),
) -> DelegationResponse:
    delegation = get_delegation(db, delegation_id)
    if delegation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
    return delegation


@router.get("/{delegation_id}/verify", response_model=DelegationVerificationResponse)
async def verify_delegation_endpoint(
    delegation_id: UUID,
    db: Session = Depends(get_db),
    principal: dict = Depends(get_current_principal),
) -> DelegationVerificationResponse:
    try:
        return await verify_delegation(db, delegation_id)
    except DelegationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")


@router.get("/{delegation_id}/chain", response_model=list[DelegationResponse])
def get_delegation_chain_endpoint(
    delegation_id: UUID,
    db: Session = Depends(get_db),
    principal: dict = Depends(get_current_principal),
) -> list[DelegationResponse]:
    try:
        return get_delegation_chain(db, delegation_id)
    except DelegationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")


@router.post("/{delegation_id}/revoke", response_model=DelegationResponse)
async def revoke_delegation_endpoint(
    delegation_id: UUID,
    request: RevocationRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> DelegationResponse:
    try:
        return await revoke_delegation(db, principal, delegation_id, request.reason)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except DelegationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegation not found")
    except InvalidDelegationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
