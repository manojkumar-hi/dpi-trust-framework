import base64
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.verifiable_credential import VerifiableCredential
from app.schemas.credential import CredentialCreate, CredentialVerificationResponse
from app.services.credential_canonicalization import (
    canonical_credential_bytes,
    credential_hash,
)
from app.services.fabric_ledger_client import FabricLedgerClient
from app.services.organization_key_service import load_private_key


class IssuerOrganizationNotFoundError(Exception):
    pass


class SubjectAgentNotFoundError(Exception):
    pass


class IssuerIdentityNotFoundError(Exception):
    pass


class SubjectIdentityNotFoundError(Exception):
    pass


class CredentialNotFoundError(Exception):
    pass


class CredentialAlreadyRevokedError(Exception):
    pass


class OrganizationSigningKeyUnavailableError(Exception):
    pass


def get_organization(db: Session, organization_id: UUID) -> Organization | None:
    return db.get(Organization, organization_id)


def get_agent(db: Session, agent_id: UUID) -> Agent | None:
    return db.get(Agent, agent_id)


def get_credential(db: Session, credential_id: UUID) -> VerifiableCredential | None:
    credential = db.get(VerifiableCredential, credential_id)
    if credential is not None:
        mark_expired(db, credential)
    return credential


def mark_expired(db: Session, credential: VerifiableCredential) -> None:
    now = datetime.now(timezone.utc)
    if (
        credential.status == "active"
        and credential.expires_at is not None
        and credential.expires_at <= now
    ):
        credential.status = "expired"
        db.commit()
        db.refresh(credential)


async def create_credential(db: Session, credential_data: CredentialCreate) -> VerifiableCredential:
    if get_organization(db, credential_data.issuer_organization_id) is None:
        raise IssuerOrganizationNotFoundError
    if get_agent(db, credential_data.subject_agent_id) is None:
        raise SubjectAgentNotFoundError
    issuer_identity = db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == credential_data.issuer_organization_id
        )
    )
    if issuer_identity is None:
        raise IssuerIdentityNotFoundError
    subject_identity = db.scalar(
        select(AgentIdentity).where(AgentIdentity.agent_id == credential_data.subject_agent_id)
    )
    if subject_identity is None:
        raise SubjectIdentityNotFoundError
    private_key = load_private_key(credential_data.issuer_organization_id)
    if private_key is None:
        raise OrganizationSigningKeyUnavailableError

    credential = VerifiableCredential(**credential_data.model_dump())
    db.add(credential)
    try:
        db.flush()
        if credential.issued_at is None:
            credential.issued_at = datetime.now(timezone.utc)
        signed_bytes = canonical_credential_bytes(
            credential.id,
            credential.issuer_organization_id,
            credential.subject_agent_id,
            credential.credential_type,
            credential.credential_data,
            credential.issued_at,
            credential.expires_at,
        )
        credential.proof_type = "Ed25519Signature2020"
        credential.signature = base64.b64encode(private_key.sign(signed_bytes)).decode("ascii")
        credential.signed_at = datetime.now(timezone.utc)
        credential_hash_value = credential_hash(
            credential.id,
            credential.issuer_organization_id,
            credential.subject_agent_id,
            credential.credential_type,
            credential.credential_data,
            credential.issued_at,
            credential.expires_at,
        )
        fabric_client = FabricLedgerClient()
        try:
            fabric_response = await fabric_client.issue_credential(
                credential_id=credential.id,
                credential_type=credential.credential_type,
                issuer_did=issuer_identity.did,
                subject_did=subject_identity.did,
                credential_hash=credential_hash_value,
                issued_at=credential.issued_at,
            )
        finally:
            await fabric_client.close()
        credential.transaction_id = fabric_response.get("transaction_id")
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(credential)
    return credential


def list_credentials(
    db: Session,
    issuer_organization_id: UUID | None = None,
    subject_agent_id: UUID | None = None,
    credential_type: str | None = None,
    status: str | None = None,
) -> list[VerifiableCredential]:
    statement = select(VerifiableCredential).order_by(VerifiableCredential.created_at)
    if issuer_organization_id is not None:
        statement = statement.where(
            VerifiableCredential.issuer_organization_id == issuer_organization_id
        )
    if subject_agent_id is not None:
        statement = statement.where(VerifiableCredential.subject_agent_id == subject_agent_id)
    if credential_type is not None:
        statement = statement.where(VerifiableCredential.credential_type == credential_type)
    if status is not None:
        statement = statement.where(VerifiableCredential.status == status)
    credentials = list(db.scalars(statement).all())
    for credential in credentials:
        mark_expired(db, credential)
    return credentials


def get_agent_credentials(db: Session, agent_id: UUID) -> list[VerifiableCredential]:
    if get_agent(db, agent_id) is None:
        raise SubjectAgentNotFoundError
    credentials = list(
        db.scalars(
            select(VerifiableCredential)
            .where(VerifiableCredential.subject_agent_id == agent_id)
            .order_by(VerifiableCredential.created_at)
        ).all()
    )
    for credential in credentials:
        mark_expired(db, credential)
    return credentials


def revoke_credential(
    db: Session, credential_id: UUID, reason: str
) -> VerifiableCredential:
    credential = get_credential(db, credential_id)
    if credential is None:
        raise CredentialNotFoundError
    if credential.status == "revoked":
        raise CredentialAlreadyRevokedError
    credential.status = "revoked"
    credential.revoked_at = datetime.now(timezone.utc)
    credential.revocation_reason = reason
    db.commit()
    db.refresh(credential)
    return credential


def verify_credential(
    db: Session, credential_id: UUID
) -> CredentialVerificationResponse:
    credential = get_credential(db, credential_id)
    if credential is None:
        raise CredentialNotFoundError

    issuer = get_organization(db, credential.issuer_organization_id)
    subject = get_agent(db, credential.subject_agent_id)
    issuer_identity = db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == credential.issuer_organization_id
        )
    )
    subject_identity = db.scalar(
        select(AgentIdentity).where(AgentIdentity.agent_id == credential.subject_agent_id)
    )

    status = credential.status
    lifecycle_valid = True
    if status == "revoked":
        lifecycle_valid = False
        message = "Credential has been revoked"
    elif status == "expired":
        lifecycle_valid = False
        message = "Credential has expired"
    elif issuer is None or subject is None:
        lifecycle_valid = False
        message = "Credential issuer or subject no longer exists"
    elif issuer_identity is None or subject_identity is None:
        lifecycle_valid = False
        message = "Credential issuer or subject identity is unavailable"
    else:
        message = "Credential lifecycle is valid"

    cryptographically_verified = False
    signature_status = "unsigned"
    if credential.signature is not None and credential.proof_type is not None:
        try:
            signed_bytes = canonical_credential_bytes(
                credential.id,
                credential.issuer_organization_id,
                credential.subject_agent_id,
                credential.credential_type,
                credential.credential_data,
                credential.issued_at,
                credential.expires_at,
            )
            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(issuer_identity.public_key) if issuer_identity else b""
            )
            public_key.verify(base64.b64decode(credential.signature), signed_bytes)
            cryptographically_verified = True
            signature_status = "valid"
        except (InvalidSignature, ValueError, TypeError):
            signature_status = "invalid"

    if credential.signature is None:
        message = "Credential has no cryptographic signature"
    elif not cryptographically_verified:
        message = "Credential signature verification failed. Credential may have been tampered with."
    elif lifecycle_valid:
        message = "Credential is valid and cryptographically verified"

    return CredentialVerificationResponse(
        credential_id=credential.id,
        credential_type=credential.credential_type,
        issuer_did=issuer_identity.did if issuer_identity is not None else None,
        subject_did=subject_identity.did if subject_identity is not None else None,
        status=status,
        lifecycle_valid=lifecycle_valid,
        cryptographically_verified=cryptographically_verified,
        signature_status=signature_status,
        proof_type=credential.proof_type,
        valid=lifecycle_valid and cryptographically_verified,
        issued_at=credential.issued_at,
        expires_at=credential.expires_at,
        revoked_at=credential.revoked_at,
        verification_message=message,
    )
