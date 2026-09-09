from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.credential import (
    CredentialCreate,
    CredentialResponse,
    CredentialRevokeRequest,
    CredentialVerificationResponse,
)
from app.services.credential_service import (
    CredentialAlreadyRevokedError,
    CredentialNotFoundError,
    IssuerIdentityNotFoundError,
    IssuerOrganizationNotFoundError,
    SubjectAgentNotFoundError,
    SubjectIdentityNotFoundError,
    create_credential,
    get_agent_credentials,
    get_credential,
    list_credentials,
    revoke_credential,
    verify_credential,
)

router = APIRouter(prefix="/credentials", tags=["Verifiable Credentials"])


@router.post(
    "",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Required issuer or subject identity is missing"},
        404: {"description": "Issuer organization or subject agent not found"},
    },
)
async def issue_credential(
    credential_data: CredentialCreate, db: Session = Depends(get_db)
) -> CredentialResponse:
    try:
        return await create_credential(db, credential_data)
    except IssuerOrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Issuer organization not found") from exc
    except SubjectAgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Subject agent not found") from exc
    except IssuerIdentityNotFoundError as exc:
        raise HTTPException(
            status_code=400, detail="Issuer organization identity is required"
        ) from exc
    except SubjectIdentityNotFoundError as exc:
        raise HTTPException(status_code=400, detail="Subject agent identity is required") from exc


@router.get("", response_model=list[CredentialResponse])
def list_credential_records(
    issuer_organization_id: UUID | None = Query(default=None),
    subject_agent_id: UUID | None = Query(default=None),
    credential_type: str | None = Query(default=None),
    credential_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[CredentialResponse]:
    return list_credentials(
        db,
        issuer_organization_id,
        subject_agent_id,
        credential_type,
        credential_status,
    )


@router.get("/{credential_id}", response_model=CredentialResponse, responses={404: {"description": "Credential not found"}})
def retrieve_credential(credential_id: UUID, db: Session = Depends(get_db)) -> CredentialResponse:
    credential = get_credential(db, credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return credential


@router.get(
    "/{credential_id}/verify",
    response_model=CredentialVerificationResponse,
    responses={404: {"description": "Credential not found"}},
)
def verify_credential_record(
    credential_id: UUID, db: Session = Depends(get_db)
) -> CredentialVerificationResponse:
    try:
        return verify_credential(db, credential_id)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Credential not found") from exc


@router.post(
    "/{credential_id}/revoke",
    response_model=CredentialResponse,
    responses={
        404: {"description": "Credential not found"},
        409: {"description": "Credential is already revoked"},
    },
)
def revoke_credential_record(
    credential_id: UUID,
    request: CredentialRevokeRequest,
    db: Session = Depends(get_db),
) -> CredentialResponse:
    try:
        return revoke_credential(db, credential_id, request.reason)
    except CredentialNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Credential not found") from exc
    except CredentialAlreadyRevokedError as exc:
        raise HTTPException(status_code=409, detail="Credential is already revoked") from exc
