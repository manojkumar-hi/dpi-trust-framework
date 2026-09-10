import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.capability_catalog import get_capability_definition
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.delegation import Delegation
from app.models.delegation_capability import DelegationCapability
from app.models.delegation_event import DelegationEvent
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.schemas.delegation import DelegationCreate
from app.services.delegation_canonicalization import (
    PROOF_TYPE,
    canonical_delegation_bytes,
    delegation_hash,
)
from app.services.fabric_ledger_client import FabricLedgerClient
from app.services.organization_key_service import load_private_key


class DelegationError(Exception):
    pass


class DelegationNotFoundError(DelegationError):
    pass


class DelegationAlreadyRevokedError(DelegationError):
    pass


class InvalidDelegationError(DelegationError):
    pass


class OrganizationSigningKeyUnavailableError(DelegationError):
    pass


@dataclass(frozen=True)
class DelegationVerificationResult:
    delegation_id: UUID
    status: str
    lifecycle_valid: bool
    signature_valid: bool
    hash_valid: bool
    principals_valid: bool
    capabilities_valid: bool
    valid: bool
    verification_message: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware_timestamps(data: DelegationCreate) -> None:
    for value in (data.starts_at, data.expires_at):
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidDelegationError("Delegation timestamps must be timezone-aware")
    if data.starts_at >= data.expires_at:
        raise InvalidDelegationError("Delegation starts_at must be before expires_at")


def validate_revocation_state(
    status: str,
    revoked_at: datetime | None,
    revocation_reason: str | None,
) -> None:
    if status == "revoked":
        if revoked_at is None:
            raise InvalidDelegationError("Revoked delegations require revoked_at")
        if revocation_reason is None or not revocation_reason.strip():
            raise InvalidDelegationError("Revoked delegations require a reason")
    elif revoked_at is not None:
        raise InvalidDelegationError("Only revoked delegations may have revoked_at")


def _get_active_organization_key(
    db: Session, identity: OrganizationIdentity
) -> OrganizationIdentityKey | None:
    return db.scalar(
        select(OrganizationIdentityKey)
        .where(OrganizationIdentityKey.organization_identity_id == identity.id)
        .where(OrganizationIdentityKey.status == "active")
    )


def _capability_payloads(data: DelegationCreate) -> list[dict[str, Any]]:
    payloads = []
    for capability in data.capabilities:
        if get_capability_definition(capability.capability_code) is None:
            raise InvalidDelegationError(
                f"Unknown capability code: {capability.capability_code}"
            )
        payloads.append(
            {
                "capabilityCode": capability.capability_code,
                "scope": capability.scope,
                "constraints": capability.constraints,
            }
        )
    return payloads


def _add_event(
    db: Session,
    delegation: Delegation,
    *,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    actor_did: str | None,
    reason: str | None = None,
) -> None:
    db.add(
        DelegationEvent(
            delegation_id=delegation.id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            actor_did=actor_did,
            reason=reason,
        )
    )


async def create_delegation(db: Session, data: DelegationCreate) -> Delegation:
    if data.parent_delegation_id is not None:
        raise InvalidDelegationError("Subdelegation creation is not supported in Module 9")
    _require_aware_timestamps(data)
    capability_payloads = _capability_payloads(data)

    organization = db.get(Organization, data.delegator_organization_id)
    agent = db.get(Agent, data.delegatee_agent_id)
    if organization is None or agent is None:
        raise InvalidDelegationError("Delegator organization and delegatee agent are required")
    if organization.status != "active" or agent.status != "active":
        raise InvalidDelegationError("Delegator organization and delegatee agent must be active")

    organization_identity = db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == organization.id
        )
    )
    agent_identity = db.scalar(
        select(AgentIdentity).where(AgentIdentity.agent_id == agent.id)
    )
    if organization_identity is None or agent_identity is None:
        raise InvalidDelegationError("Delegator and delegatee identities are required")
    if organization_identity.status != "active" or agent_identity.status != "active":
        raise InvalidDelegationError("Delegator and delegatee identities must be active")

    active_key = _get_active_organization_key(db, organization_identity)
    verification_method = (
        active_key.verification_method
        if active_key is not None
        else f"{organization_identity.did}#key-1"
    )
    signing_public_key = (
        active_key.public_key if active_key is not None else organization_identity.public_key
    )
    private_key = load_private_key(organization.id)
    if private_key is None:
        raise OrganizationSigningKeyUnavailableError

    delegation_id = uuid4()
    issued_at = _utc_now()
    delegation = Delegation(
        id=delegation_id,
        delegator_organization_id=organization.id,
        delegatee_agent_id=agent.id,
        delegator_did=organization_identity.did,
        delegatee_did=agent_identity.did,
        parent_delegation_id=None,
        root_delegation_id=delegation_id,
        depth=0,
        purpose=data.purpose,
        starts_at=data.starts_at,
        expires_at=data.expires_at,
        status="active",
        proof_type=PROOF_TYPE,
        verification_method=verification_method,
        signing_public_key=signing_public_key,
        signed_at=issued_at,
        signature="pending",
        canonical_hash="0" * 64,
    )
    db.add(delegation)
    try:
        db.flush()
        signed_bytes = canonical_delegation_bytes(
            delegation_id=delegation.id,
            delegator_did=delegation.delegator_did,
            delegatee_did=delegation.delegatee_did,
            parent_delegation_id=delegation.parent_delegation_id,
            root_delegation_id=delegation.root_delegation_id,
            depth=delegation.depth,
            purpose=delegation.purpose,
            starts_at=delegation.starts_at,
            expires_at=delegation.expires_at,
            issued_at=delegation.signed_at,
            capabilities=capability_payloads,
        )
        delegation.signature = base64.b64encode(private_key.sign(signed_bytes)).decode("ascii")
        delegation.canonical_hash = delegation_hash(
            delegation_id=delegation.id,
            delegator_did=delegation.delegator_did,
            delegatee_did=delegation.delegatee_did,
            parent_delegation_id=delegation.parent_delegation_id,
            root_delegation_id=delegation.root_delegation_id,
            depth=delegation.depth,
            purpose=delegation.purpose,
            starts_at=delegation.starts_at,
            expires_at=delegation.expires_at,
            issued_at=delegation.signed_at,
            capabilities=capability_payloads,
        )
        for capability in capability_payloads:
            delegation.capabilities.append(
                DelegationCapability(
                    capability_code=capability["capabilityCode"],
                    scope=capability["scope"],
                    constraints=capability["constraints"],
                )
            )
        
        fabric_client = FabricLedgerClient()
        try:
            fabric_response = await fabric_client.issue_delegation(
                delegation_id=delegation.id,
                delegator_did=delegation.delegator_did,
                delegatee_did=delegation.delegatee_did,
                canonical_hash=delegation.canonical_hash,
                issued_at=delegation.signed_at,
                expires_at=delegation.expires_at,
            )
        finally:
            await fabric_client.close()
        
        delegation.fabric_transaction_id = fabric_response.get("transaction_id")
        
        _add_event(
            db,
            delegation,
            event_type="created",
            from_status=None,
            to_status="active",
            actor_did=organization_identity.did,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(delegation)
    return delegation


def _delegation_payloads(delegation: Delegation) -> list[dict[str, Any]]:
    return [
        {
            "capabilityCode": capability.capability_code,
            "scope": capability.scope,
            "constraints": capability.constraints,
        }
        for capability in delegation.capabilities
    ]


def _canonical_bytes_for_delegation(delegation: Delegation) -> bytes:
    return canonical_delegation_bytes(
        delegation_id=delegation.id,
        delegator_did=delegation.delegator_did,
        delegatee_did=delegation.delegatee_did,
        parent_delegation_id=delegation.parent_delegation_id,
        root_delegation_id=delegation.root_delegation_id,
        depth=delegation.depth,
        purpose=delegation.purpose,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        issued_at=delegation.signed_at,
        capabilities=_delegation_payloads(delegation),
    )


def _refresh_expiry(db: Session, delegation: Delegation) -> None:
    if delegation.status == "active" and delegation.expires_at <= _utc_now():
        delegation.status = "expired"
        _add_event(
            db,
            delegation,
            event_type="expired",
            from_status="active",
            to_status="expired",
            actor_did=None,
        )
        db.commit()
        db.refresh(delegation)


async def verify_delegation(db: Session, delegation_id: UUID) -> DelegationVerificationResult:
    delegation = db.get(Delegation, delegation_id)
    if delegation is None:
        raise DelegationNotFoundError
    _refresh_expiry(db, delegation)

    organization = db.get(Organization, delegation.delegator_organization_id)
    agent = db.get(Agent, delegation.delegatee_agent_id)
    organization_identity = db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == delegation.delegator_organization_id
        )
    )
    agent_identity = db.scalar(
        select(AgentIdentity).where(AgentIdentity.agent_id == delegation.delegatee_agent_id)
    )
    principals_valid = bool(
        organization
        and agent
        and organization_identity
        and agent_identity
        and organization.status == "active"
        and agent.status == "active"
        and organization_identity.status == "active"
        and agent_identity.status == "active"
        and organization_identity.did == delegation.delegator_did
        and agent_identity.did == delegation.delegatee_did
    )

    canonical_bytes = _canonical_bytes_for_delegation(delegation)
    calculated_hash = delegation_hash(
        delegation_id=delegation.id,
        delegator_did=delegation.delegator_did,
        delegatee_did=delegation.delegatee_did,
        parent_delegation_id=delegation.parent_delegation_id,
        root_delegation_id=delegation.root_delegation_id,
        depth=delegation.depth,
        purpose=delegation.purpose,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        issued_at=delegation.signed_at,
        capabilities=_delegation_payloads(delegation),
    )
    hash_valid = calculated_hash == delegation.canonical_hash
    capabilities_valid = all(
        get_capability_definition(capability.capability_code) is not None
        for capability in delegation.capabilities
    )
    signature_valid = False
    try:
        if organization_identity is None or not delegation.verification_method.startswith(
            f"{delegation.delegator_did}#"
        ):
            raise ValueError
        public_key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(delegation.signing_public_key)
        )
        public_key.verify(base64.b64decode(delegation.signature), canonical_bytes)
        signature_valid = True
    except (InvalidSignature, ValueError, TypeError):
        signature_valid = False

    lifecycle_valid = (
        delegation.status == "active"
        and delegation.starts_at <= _utc_now() < delegation.expires_at
    )
    valid = (
        lifecycle_valid
        and signature_valid
        and hash_valid
        and principals_valid
        and capabilities_valid
    )
    message = "Delegation is valid and cryptographically verified" if valid else "Delegation verification failed"

    fabric_client = FabricLedgerClient()
    try:
        fabric_response = await fabric_client.verify_delegation(
            delegation_id=delegation.id,
            canonical_hash=calculated_hash,
        )
    finally:
        await fabric_client.close()
    
    fabric_result = fabric_response.get("result", {})
    fabric_valid = fabric_result.get("valid") is True
    
    valid = valid and fabric_valid
    if not fabric_valid:
        message = f"Fabric validation failed: {fabric_result.get('reason', 'Unknown error')}"

    return DelegationVerificationResult(
        delegation_id=delegation.id,
        status=delegation.status,
        lifecycle_valid=lifecycle_valid,
        signature_valid=signature_valid,
        hash_valid=hash_valid,
        principals_valid=principals_valid,
        capabilities_valid=capabilities_valid,
        valid=valid,
        verification_message=message,
    )


async def revoke_delegation(db: Session, delegation_id: UUID, reason: str) -> Delegation:
    delegation = db.get(Delegation, delegation_id)
    if delegation is None:
        raise DelegationNotFoundError
    if delegation.status == "revoked":
        raise DelegationAlreadyRevokedError
    if not reason.strip():
        raise InvalidDelegationError("Revocation reason is required")

    revoked_at = _utc_now()
    validate_revocation_state("revoked", revoked_at, reason)
    
    fabric_client = FabricLedgerClient()
    try:
        await fabric_client.revoke_delegation(
            delegation_id=delegation.id,
            reason=reason,
            revoked_at=revoked_at,
        )
    finally:
        await fabric_client.close()

    previous_status = delegation.status
    delegation.status = "revoked"
    delegation.revoked_at = revoked_at
    delegation.revocation_reason = reason
    _add_event(
        db,
        delegation,
        event_type="revoked",
        from_status=previous_status,
        to_status="revoked",
        actor_did=delegation.delegator_did,
        reason=reason,
    )
    db.commit()
    db.refresh(delegation)
    return delegation


def get_delegation(db: Session, delegation_id: UUID) -> Delegation | None:
    return db.get(Delegation, delegation_id)


def get_delegations(
    db: Session,
    organization_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> list[Delegation]:
    query = select(Delegation)
    if organization_id is not None:
        query = query.where(Delegation.delegator_organization_id == organization_id)
    if agent_id is not None:
        query = query.where(Delegation.delegatee_agent_id == agent_id)
    return list(db.scalars(query).all())


def get_delegation_chain(db: Session, delegation_id: UUID) -> list[Delegation]:
    delegation = db.get(Delegation, delegation_id)
    if delegation is None:
        raise DelegationNotFoundError

    chain = []
    current = delegation
    while current is not None:
        chain.append(current)
        if current.parent_delegation_id is None:
            break
        current = db.get(Delegation, current.parent_delegation_id)
    
    return chain