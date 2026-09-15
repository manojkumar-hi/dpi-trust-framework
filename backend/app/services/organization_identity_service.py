import base64
from datetime import datetime, timezone
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.schemas.agent_identity import DIDResolutionResponse
from app.services.organization_key_service import save_private_key


class OrganizationNotFoundError(Exception):
    pass


class OrganizationIdentityAlreadyExistsError(Exception):
    pass


def generate_organization_did(domain: str) -> str:
    return f"did:web:{domain}"


def get_organization(db: Session, organization_id: UUID) -> Organization | None:
    return db.get(Organization, organization_id)


def get_organization_identity(
    db: Session, organization_id: UUID
) -> OrganizationIdentity:
    if get_organization(db, organization_id) is None:
        raise OrganizationNotFoundError

    identity = db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == organization_id
        )
    )
    if identity is None:
        raise LookupError
    return identity


def create_organization_identity(
    db: Session, organization_id: UUID
) -> OrganizationIdentity:
    organization = get_organization(db, organization_id)
    if organization is None:
        raise OrganizationNotFoundError
    if db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == organization_id
        )
    ) is not None:
        raise OrganizationIdentityAlreadyExistsError

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    now = datetime.now(timezone.utc)
    identity = OrganizationIdentity(
        organization_id=organization_id,
        did=generate_organization_did(organization.domain),
        public_key=base64.b64encode(public_key).decode("ascii"),
    )
    identity.keys.append(
        OrganizationIdentityKey(
            verification_method=f"{identity.did}#key-1",
            public_key=identity.public_key,
            valid_from=now,
        )
    )
    save_private_key(organization_id, private_key)
    db.add(identity)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OrganizationIdentityAlreadyExistsError from exc
    db.refresh(identity)
    return identity


def rekey_organization_identity(
    db: Session, organization_id: UUID
) -> OrganizationIdentity:
    if get_organization(db, organization_id) is None:
        raise OrganizationNotFoundError
    identity = db.scalar(
        select(OrganizationIdentity).where(
            OrganizationIdentity.organization_id == organization_id
        )
    )
    if identity is None:
        raise LookupError

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    now = datetime.now(timezone.utc)
    previous_key = db.scalar(
        select(OrganizationIdentityKey)
        .where(OrganizationIdentityKey.organization_identity_id == identity.id)
        .where(OrganizationIdentityKey.status == "active")
    )
    next_key_number = len(identity.keys) + 1
    if previous_key is not None:
        previous_key.status = "retired"
        previous_key.valid_until = now
    save_private_key(organization_id, private_key)
    identity.public_key = base64.b64encode(public_key).decode("ascii")
    identity.keys.append(
        OrganizationIdentityKey(
            verification_method=f"{identity.did}#key-{next_key_number}",
            public_key=identity.public_key,
            valid_from=now,
        )
    )
    identity.updated_at = now
    db.commit()
    db.refresh(identity)
    return identity


def resolve_organization_did(
    db: Session, did: str
) -> DIDResolutionResponse | None:
    from sqlalchemy.orm import selectinload
    identity = db.scalar(
        select(OrganizationIdentity)
        .options(selectinload(OrganizationIdentity.keys))
        .where(OrganizationIdentity.did == did)
    )
    if identity is None:
        return None

    verification_methods = []
    authentication_methods = []
    
    # Sort keys for deterministic output, retired keys still go in verification_methods
    for key in sorted(identity.keys, key=lambda k: k.created_at):
        vm = {
            "id": key.verification_method,
            "type": "Ed25519VerificationKey2020",
            "controller": identity.did,
            "publicKeyBase64": key.public_key,
        }
        verification_methods.append(vm)
        if key.status == "active":
            authentication_methods.append(key.verification_method)

    # Legacy fallback if no keys exist (should not happen in prod after migration)
    if not verification_methods:
        vm_id = f"{identity.did}#key-1"
        verification_methods.append({
            "id": vm_id,
            "type": "Ed25519VerificationKey2020",
            "controller": identity.did,
            "publicKeyBase64": identity.public_key,
        })
        authentication_methods.append(vm_id)

    return DIDResolutionResponse(
        **{
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": identity.did,
            "verificationMethod": verification_methods,
            "authentication": authentication_methods,
            "assertionMethod": authentication_methods, # Same active keys for assertions
            "status": identity.status,
        }
    )
