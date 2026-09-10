import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.delegation import Delegation
from app.models.delegation_capability import DelegationCapability
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.schemas.delegation import DelegationCapabilityCreate, DelegationCreate
from app.services import delegation_service
from app.services.delegation_canonicalization import (
    canonical_delegation_bytes,
    delegation_hash,
)


def _public_key(private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")


class FakeSession:
    def __init__(self, organization, agent, organization_identity, agent_identity, key=None):
        self.organization = organization
        self.agent = agent
        self.organization_identity = organization_identity
        self.agent_identity = agent_identity
        self.key = key
        self.delegation = None
        self.events = []

    def get(self, model, identifier):
        if model is Organization:
            return self.organization if self.organization and self.organization.id == identifier else None
        if model is Agent:
            return self.agent if self.agent.id == identifier else None
        if model is Delegation:
            return self.delegation if self.delegation and self.delegation.id == identifier else None
        return None

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is OrganizationIdentity:
            return self.organization_identity
        if entity is AgentIdentity:
            return self.agent_identity
        if entity is OrganizationIdentityKey:
            return self.key
        return None

    def add(self, value):
        if isinstance(value, Delegation):
            self.delegation = value
        else:
            self.events.append(value)

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def refresh(self, value):
        return None


def _identities(private_key=None):
    organization_id = uuid4()
    agent_id = uuid4()
    organization = Organization(id=organization_id, name="Org", domain="org.example", status="active")
    agent = Agent(id=agent_id, organization_id=organization_id, name="Agent", agent_type="worker", status="active")
    organization_identity = OrganizationIdentity(
        id=uuid4(),
        organization_id=organization_id,
        did=f"did:dpi:org:{organization_id}",
        public_key=_public_key(private_key or Ed25519PrivateKey.generate()),
        status="active",
    )
    agent_identity = AgentIdentity(
        id=uuid4(),
        agent_id=agent_id,
        did=f"did:dpi:{agent_id}",
        public_key="agent-public-key",
        status="active",
    )
    return organization, agent, organization_identity, agent_identity


def _request(organization, agent, *, starts_at=None, expires_at=None, capability="agent.read"):
    now = datetime.now(timezone.utc)
    return DelegationCreate(
        delegator_organization_id=organization.id,
        delegatee_agent_id=agent.id,
        purpose="Read agent metadata",
        starts_at=starts_at or now - timedelta(minutes=1),
        expires_at=expires_at or now + timedelta(hours=1),
        capabilities=[DelegationCapabilityCreate(capability_code=capability)],
    )


def _signed_delegation(private_key=None, expires_at=None):
    private_key = private_key or Ed25519PrivateKey.generate()
    organization, agent, organization_identity, agent_identity = _identities(private_key)
    now = datetime.now(timezone.utc)
    delegation = Delegation(
        id=uuid4(),
        delegator_organization_id=organization.id,
        delegatee_agent_id=agent.id,
        delegator_did=organization_identity.did,
        delegatee_did=agent_identity.did,
        root_delegation_id=uuid4(),
        depth=0,
        purpose="Read agent metadata",
        starts_at=now - timedelta(minutes=1),
        expires_at=expires_at or now + timedelta(hours=1),
        status="active",
        proof_type="Ed25519Signature2020",
        verification_method=f"{organization_identity.did}#key-1",
        signing_public_key=_public_key(private_key),
        signed_at=now,
        signature="",
        canonical_hash="",
    )
    delegation.capabilities.append(
        DelegationCapability(capability_code="agent.read", scope={}, constraints={})
    )
    payload = {
        "capabilityCode": "agent.read",
        "scope": {},
        "constraints": {},
    }
    canonical_bytes = canonical_delegation_bytes(
        delegation_id=delegation.id,
        delegator_did=delegation.delegator_did,
        delegatee_did=delegation.delegatee_did,
        parent_delegation_id=None,
        root_delegation_id=delegation.root_delegation_id,
        depth=delegation.depth,
        purpose=delegation.purpose,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        issued_at=delegation.signed_at,
        capabilities=[payload],
    )
    delegation.signature = base64.b64encode(private_key.sign(canonical_bytes)).decode("ascii")
    delegation.canonical_hash = delegation_hash(
        delegation_id=delegation.id,
        delegator_did=delegation.delegator_did,
        delegatee_did=delegation.delegatee_did,
        parent_delegation_id=None,
        root_delegation_id=delegation.root_delegation_id,
        depth=delegation.depth,
        purpose=delegation.purpose,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        issued_at=delegation.signed_at,
        capabilities=[payload],
    )
    return delegation, organization, agent, organization_identity, agent_identity


def test_canonicalization_and_hash_are_deterministic():
    delegation_id = uuid4()
    root_id = uuid4()
    first = canonical_delegation_bytes(
        delegation_id=delegation_id,
        delegator_did="did:dpi:org:1",
        delegatee_did="did:dpi:agent:1",
        parent_delegation_id=None,
        root_delegation_id=root_id,
        depth=0,
        purpose="Read",
        starts_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        issued_at=datetime(2025, 12, 31, 0, 0, tzinfo=timezone.utc),
        capabilities=[
            {"capabilityCode": "agent.read", "scope": {"b": 2, "a": 1}, "constraints": {}},
            {"capabilityCode": "credential.read", "scope": {}, "constraints": {"x": True}},
        ],
    )
    second = canonical_delegation_bytes(
        delegation_id=delegation_id,
        delegator_did="did:dpi:org:1",
        delegatee_did="did:dpi:agent:1",
        parent_delegation_id=None,
        root_delegation_id=root_id,
        depth=0,
        purpose="Read",
        starts_at=datetime(2025, 12, 31, 19, 0, tzinfo=timezone(timedelta(hours=-5))),
        expires_at=datetime(2026, 1, 1, 19, 0, tzinfo=timezone(timedelta(hours=-5))),
        issued_at=datetime(2025, 12, 30, 19, 0, tzinfo=timezone(timedelta(hours=-5))),
        capabilities=[
            {"constraints": {"x": True}, "scope": {}, "capabilityCode": "credential.read"},
            {"constraints": {}, "scope": {"a": 1, "b": 2}, "capabilityCode": "agent.read"},
        ],
    )
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
    assert "signature" not in first.decode("utf-8")
    assert "fabricTransactionId" not in first.decode("utf-8")
    assert delegation_hash(
        delegation_id=delegation_id,
        delegator_did="did:dpi:org:1",
        delegatee_did="did:dpi:agent:1",
        parent_delegation_id=None,
        root_delegation_id=root_id,
        depth=0,
        purpose="Read",
        starts_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc),
        issued_at=datetime(2025, 12, 31, 0, 0, tzinfo=timezone.utc),
        capabilities=[],
    ) != ""


@pytest.mark.asyncio
async def test_create_and_verify_valid_signed_delegation(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    organization, agent, organization_identity, agent_identity = _identities(private_key)
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=organization_identity.id,
        verification_method=f"{organization_identity.did}#key-1",
        public_key=_public_key(private_key),
        status="active",
        valid_from=datetime.now(timezone.utc),
    )
    db = FakeSession(organization, agent, organization_identity, agent_identity, key)
    monkeypatch.setattr(delegation_service, "load_private_key", lambda _: private_key)
    delegation = await delegation_service.create_delegation(db, _request(organization, agent))
    result = await delegation_service.verify_delegation(db, delegation.id)
    assert result.valid is True
    assert result.signature_valid is True
    assert any(event.event_type == "created" for event in db.events)


@pytest.mark.asyncio
async def test_tampered_delegation_is_rejected():
    delegation, organization, agent, organization_identity, agent_identity = _signed_delegation()
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    db.delegation = delegation
    delegation.purpose = "Tampered"
    result = await delegation_service.verify_delegation(db, delegation.id)
    assert result.valid is False
    assert result.signature_valid is False
    assert result.hash_valid is False


@pytest.mark.asyncio
async def test_historical_key_snapshot_verifies_after_rekey():
    old_key = Ed25519PrivateKey.generate()
    delegation, organization, agent, organization_identity, agent_identity = _signed_delegation(old_key)
    organization_identity.public_key = _public_key(Ed25519PrivateKey.generate())
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    db.delegation = delegation
    result = await delegation_service.verify_delegation(db, delegation.id)
    assert result.valid is True


@pytest.mark.asyncio
async def test_invalid_principals_and_inactive_identities_are_rejected():
    private_key = Ed25519PrivateKey.generate()
    organization, agent, organization_identity, agent_identity = _identities(private_key)
    db = FakeSession(None, agent, organization_identity, agent_identity)
    with pytest.raises(delegation_service.InvalidDelegationError):
        await delegation_service.create_delegation(db, _request(organization, agent))

    organization.status = "inactive"
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    with pytest.raises(delegation_service.InvalidDelegationError):
        await delegation_service.create_delegation(db, _request(organization, agent))

    organization.status = "active"
    organization_identity.status = "inactive"
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    with pytest.raises(delegation_service.InvalidDelegationError):
        await delegation_service.create_delegation(db, _request(organization, agent))


@pytest.mark.asyncio
async def test_invalid_time_range_and_unknown_capability_are_rejected():
    organization, agent, organization_identity, agent_identity = _identities()
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    now = datetime.now(timezone.utc)
    with pytest.raises(delegation_service.InvalidDelegationError):
        await delegation_service.create_delegation(
            db, _request(organization, agent, starts_at=now, expires_at=now)
        )
    with pytest.raises(delegation_service.InvalidDelegationError):
        await delegation_service.create_delegation(
            db, _request(organization, agent, capability="unknown.action")
        )


@pytest.mark.asyncio
async def test_expiry_creates_lifecycle_event():
    delegation, organization, agent, organization_identity, agent_identity = _signed_delegation(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    db.delegation = delegation
    result = await delegation_service.verify_delegation(db, delegation.id)
    assert result.status == "expired"
    assert result.lifecycle_valid is False
    assert any(event.event_type == "expired" for event in db.events)


@pytest.mark.asyncio
async def test_revocation_and_revocation_state_validation():
    delegation, organization, agent, organization_identity, agent_identity = _signed_delegation()
    db = FakeSession(organization, agent, organization_identity, agent_identity)
    db.delegation = delegation
    revoked = await delegation_service.revoke_delegation(db, delegation.id, "Compromised")
    assert revoked.status == "revoked"
    assert revoked.revoked_at is not None
    assert any(event.event_type == "revoked" for event in db.events)

    with pytest.raises(delegation_service.InvalidDelegationError):
        delegation_service.validate_revocation_state("revoked", None, "reason")
    with pytest.raises(delegation_service.InvalidDelegationError):
        delegation_service.validate_revocation_state("revoked", datetime.now(timezone.utc), "")
    with pytest.raises(delegation_service.InvalidDelegationError):
        delegation_service.validate_revocation_state(
            "active", datetime.now(timezone.utc), None
        )