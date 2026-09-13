from typing import Optional
from sqlalchemy.orm import Session
from app.api.dependencies import Principal
from app.models.organization_identity import OrganizationIdentity
from app.models.agent_identity import AgentIdentity
from app.core.auth import AuthError, IDENTITY_NOT_FOUND, IDENTITY_REVOKED, IDENTITY_MISMATCH, IDENTITY_AMBIGUOUS

def resolve_identity_binding(
    db: Session, 
    iss: str, 
    sub: str,
    dpi_org_id: Optional[str] = None,
    dpi_agent_id: Optional[str] = None
) -> Principal:
    """
    Resolves the canonical (iss, sub) JWT identity to a framework Principal.
    Enforces that the mapping is unambiguous and validates any custom hints (dpi_org_id, dpi_agent_id).
    """
    # Find all matches across both Identity tables
    agent_id_records = db.query(AgentIdentity).filter(
        AgentIdentity.authentication_issuer == iss,
        AgentIdentity.authentication_subject == sub
    ).all()

    org_id_records = db.query(OrganizationIdentity).filter(
        OrganizationIdentity.authentication_issuer == iss,
        OrganizationIdentity.authentication_subject == sub
    ).all()
    
    total_matches = len(agent_id_records) + len(org_id_records)
    
    if total_matches == 0:
        raise AuthError(IDENTITY_NOT_FOUND, "No framework identity bound to this subject")
        
    if total_matches > 1:
        raise AuthError(IDENTITY_AMBIGUOUS, "Ambiguous identity binding: multiple records match (iss, sub)")
        
    # We have exactly one match
    principal = None
    
    if agent_id_records:
        agent_id_record = agent_id_records[0]
        if agent_id_record.status != "active":
            raise AuthError(IDENTITY_REVOKED, "Agent identity is not active")
        
        agent = agent_id_record.agent
        if not agent or agent.status != "active":
            raise AuthError(IDENTITY_REVOKED, "Agent is not active")
            
        principal = Principal(
            organization_id=agent.organization_id,
            agent_id=agent.id,
            subject=sub,
            scopes=[]
        )
    else:
        org_id_record = org_id_records[0]
        if org_id_record.status != "active":
            raise AuthError(IDENTITY_REVOKED, "Organization identity is not active")
            
        org = org_id_record.organization
        if not org or org.status != "active":
            raise AuthError(IDENTITY_REVOKED, "Organization is not active")
            
        principal = Principal(
            organization_id=org.id,
            agent_id=None,
            subject=sub,
            scopes=[]
        )
        
    # Validate custom hints if provided
    if dpi_org_id and str(principal.organization_id) != dpi_org_id:
        raise AuthError(IDENTITY_MISMATCH, "dpi_org_id claim conflicts with authoritative identity binding")
        
    if dpi_agent_id:
        if principal.agent_id is None or str(principal.agent_id) != dpi_agent_id:
            raise AuthError(IDENTITY_MISMATCH, "dpi_agent_id claim conflicts with authoritative identity binding")
            
    return principal
