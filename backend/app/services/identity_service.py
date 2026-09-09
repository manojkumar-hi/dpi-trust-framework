import base64
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.schemas.agent_identity import DIDResolutionResponse


class IdentityAlreadyExistsError(Exception):
    pass


def generate_did(agent_id: UUID) -> str:
    return f"did:dpi:{agent_id}"


def get_agent(db: Session, agent_id: UUID) -> Agent | None:
    return db.get(Agent, agent_id)


def get_identity_for_agent(db: Session, agent_id: UUID) -> AgentIdentity | None:
    return db.scalar(select(AgentIdentity).where(AgentIdentity.agent_id == agent_id))


def create_identity(db: Session, agent_id: UUID) -> AgentIdentity:
    if get_identity_for_agent(db, agent_id) is not None:
        raise IdentityAlreadyExistsError

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    identity = AgentIdentity(
        agent_id=agent_id,
        did=generate_did(agent_id),
        public_key=base64.b64encode(public_key).decode("ascii"),
    )
    db.add(identity)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise IdentityAlreadyExistsError from exc
    db.refresh(identity)
    return identity


def resolve_did(db: Session, did: str) -> DIDResolutionResponse | None:
    identity = db.scalar(select(AgentIdentity).where(AgentIdentity.did == did))
    if identity is None:
        return None

    verification_method_id = f"{identity.did}#key-1"
    return DIDResolutionResponse(
        **{
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": identity.did,
            "verificationMethod": [
                {
                    "id": verification_method_id,
                    "type": "Ed25519VerificationKey2020",
                    "controller": identity.did,
                    "publicKeyBase64": identity.public_key,
                }
            ],
            "authentication": [verification_method_id],
            "status": identity.status,
        }
    )
