import base64
from datetime import datetime, timezone
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.agent_identity_key import AgentIdentityKey
from app.schemas.agent_identity import DIDResolutionResponse


class IdentityAlreadyExistsError(Exception):
    pass


def generate_did(agent_id: UUID, organization_domain: str) -> str:
    return f"did:web:{organization_domain}:agents:{agent_id}"


def get_agent(db: Session, agent_id: UUID) -> Agent | None:
    return db.get(Agent, agent_id)


def get_identity_for_agent(db: Session, agent_id: UUID) -> AgentIdentity | None:
    return db.scalar(select(AgentIdentity).where(AgentIdentity.agent_id == agent_id))


def create_identity(db: Session, agent_id: UUID) -> AgentIdentity:
    if get_identity_for_agent(db, agent_id) is not None:
        raise IdentityAlreadyExistsError

    agent = get_agent(db, agent_id)
    if agent is None or agent.organization is None:
        raise ValueError("Agent or Organization not found")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    now = datetime.now(timezone.utc)

    identity = AgentIdentity(
        agent_id=agent_id,
        did=generate_did(agent_id, agent.organization.domain),
        public_key=public_key_b64, # Legacy column, populated for migration backwards compatibility
    )
    identity.keys.append(
        AgentIdentityKey(
            verification_method=f"{identity.did}#key-1",
            public_key=public_key_b64,
            valid_from=now,
        )
    )
    db.add(identity)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise IdentityAlreadyExistsError from exc
    db.refresh(identity)
    return identity


def rekey_identity(db: Session, agent_id: UUID) -> AgentIdentity:
    identity = get_identity_for_agent(db, agent_id)
    if identity is None:
        raise ValueError("Agent identity not found")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    now = datetime.now(timezone.utc)

    previous_key = db.scalar(
        select(AgentIdentityKey)
        .where(AgentIdentityKey.agent_identity_id == identity.id)
        .where(AgentIdentityKey.status == "active")
    )
    next_key_number = len(identity.keys) + 1
    if previous_key is not None:
        previous_key.status = "retired"
        previous_key.valid_until = now

    identity.public_key = public_key_b64  # keep legacy in sync for now
    identity.keys.append(
        AgentIdentityKey(
            verification_method=f"{identity.did}#key-{next_key_number}",
            public_key=public_key_b64,
            valid_from=now,
        )
    )
    identity.updated_at = now
    db.commit()
    db.refresh(identity)
    return identity


def resolve_did(db: Session, did: str) -> DIDResolutionResponse | None:
    from sqlalchemy.orm import selectinload
    identity = db.scalar(
        select(AgentIdentity)
        .options(selectinload(AgentIdentity.keys))
        .where(AgentIdentity.did == did)
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
    if not verification_methods and identity.public_key:
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
            "assertionMethod": authentication_methods,
            "status": identity.status,
        }
    )
