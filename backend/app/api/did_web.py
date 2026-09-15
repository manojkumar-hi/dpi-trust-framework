from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.agent_identity import DIDResolutionResponse
from app.services.identity_service import resolve_did as resolve_agent_did
from app.services.organization_identity_service import resolve_organization_did


router = APIRouter(tags=["DID Web Resolution"])


def _get_hostname(request: Request) -> str:
    """Extract domain from the Host header, falling back to URL hostname."""
    host_header = request.headers.get("host", "")
    # Strip port if present
    hostname = host_header.split(":")[0] if host_header else ""
    return hostname or request.url.hostname or "localhost"


@router.get("/.well-known/did.json", response_model=DIDResolutionResponse)
def resolve_org_did(
    request: Request,
    db: Session = Depends(get_db)
) -> DIDResolutionResponse:
    """
    Standard did:web endpoint for resolving the Organization's DID Document.
    """
    domain = _get_hostname(request)
    did = f"did:web:{domain}"
    
    did_doc = resolve_organization_did(db, did)
    if did_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DID document not found for {did}"
        )
    return did_doc


@router.get("/agents/{agent_id}/did.json", response_model=DIDResolutionResponse)
def resolve_agent_did_endpoint(
    request: Request,
    agent_id: UUID,
    db: Session = Depends(get_db)
) -> DIDResolutionResponse:
    """
    Standard did:web endpoint for resolving an Agent's DID Document.
    """
    domain = _get_hostname(request)
    did = f"did:web:{domain}:agents:{agent_id}"
    
    did_doc = resolve_agent_did(db, did)
    if did_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DID document not found for {did}"
        )
    return did_doc
