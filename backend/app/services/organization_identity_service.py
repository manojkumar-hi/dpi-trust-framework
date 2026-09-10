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


def generate_organization_did(organization_id: UUID) -> str:
    return f"did:dpi:org:{organization_id}"


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
    if get_organization(db, organization_id) is None:
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
        did=generate_organization_did(organization_id),
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
    identity = db.scalar(
        select(OrganizationIdentity).where(OrganizationIdentity.did == did)
    )
    if identity is None:
        return None

    active_key = next(
        (key for key in identity.keys if key.status == "active"),
        None,
    )
    verification_method_id = (
        active_key.verification_method if active_key is not None else f"{identity.did}#key-1"
    )
    public_key = active_key.public_key if active_key is not None else identity.public_key
    return DIDResolutionResponse(
        **{
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": identity.did,
            "verificationMethod": [
                {
                    "id": verification_method_id,
                    "type": "Ed25519VerificationKey2020",
                    "controller": identity.did,
                    "publicKeyBase64": public_key,
                }
            ],
            "authentication": [verification_method_id],
            "status": identity.status,
        }
    )
