import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.database.base import Base
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.models.organization import Organization
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.delegation import Delegation
from app.models.delegation_capability import DelegationCapability
from app.api.dependencies import get_current_principal, Principal
from app.services.action_orchestrator_service import ActionOrchestratorService
from app.services.delegation_service import create_delegation
from app.schemas.delegation import DelegationCreate, DelegationCapabilityCreate
from app.core.capability_catalog import CAPABILITY_CATALOG
import app.services.delegation_service

from unittest.mock import patch, AsyncMock, MagicMock

# SQLite setup
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()

# SQLite TZ fix for verify_delegation
original_verify = app.services.delegation_service.verify_delegation
async def patched_verify_delegation(db_session, delegation_id):
    delegation = db_session.get(Delegation, delegation_id)
    if delegation:
        for attr in ['starts_at', 'expires_at', 'signed_at', 'created_at', 'updated_at', 'revoked_at']:
            val = getattr(delegation, attr)
            if val and val.tzinfo is None:
                setattr(delegation, attr, val.replace(tzinfo=timezone.utc))
        keys = db_session.query(OrganizationIdentityKey).all()
        for k in keys:
            for attr in ['valid_from', 'valid_until']:
                val = getattr(k, attr)
                if val and val.tzinfo is None:
                    setattr(k, attr, val.replace(tzinfo=timezone.utc))
    return await original_verify(db_session, delegation_id)


from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64
private_key_mock = Ed25519PrivateKey.generate()

@pytest.fixture(autouse=True)
def setup_patches(monkeypatch):
    monkeypatch.setattr("app.services.delegation_service.verify_delegation", patched_verify_delegation)
    
    # Mock VP Auth
    mock_verify_vp = MagicMock()
    monkeypatch.setattr("app.services.action_orchestrator_service.verify_vp_and_consume_challenge", mock_verify_vp)
    
    # Mock TrustService
    from app.schemas.trust import TrustScoreResponse
    mock_trust = MagicMock()
    mock_trust.return_value = TrustScoreResponse(
        agent_id=uuid4(),
        trust=0.9, belief=0.9, disbelief=0.0, uncertainty=0.1, recent_risk=0.0, positive_evidence=10.0, negative_evidence=0.0
    )
    monkeypatch.setattr("app.services.action_orchestrator_service.TrustService.get_trust_score", mock_trust)
    
    # Mock Ingest Evidence
    mock_ingest = MagicMock()
    monkeypatch.setattr("app.services.action_orchestrator_service.TrustService.ingest_evidence", mock_ingest)
    
    # Mock AuditService
    mock_audit = MagicMock()
    monkeypatch.setattr("app.services.action_orchestrator_service.AuditService.create_audit_record", mock_audit)

    # Mock load_private_key in both places
    monkeypatch.setattr("app.services.delegation_service.load_private_key", lambda _: private_key_mock)
    monkeypatch.setattr("app.services.status_list_service.load_private_key", lambda _: private_key_mock)
    
    # Register dummy adapter for tests
    from app.services.agent_adapters import registry
    from app.services.agent_adapters.base import AgentRuntimeAdapter, AgentExecutionResult
    class DummyAdapter(AgentRuntimeAdapter):
        async def can_handle(self, action_type: str, payload: dict) -> bool:
            return action_type in ["verifiable_credential.issue", "delegation.revoke"]
        async def execute_action(self, target_agent_id, action_type, payload, **kwargs):
            return AgentExecutionResult(status="SUCCESS", data={"dummy": "data"})
            
    registry.register_adapter(DummyAdapter())

@pytest.fixture
def test_data(db):
    org_id = uuid4()
    agent_id = uuid4()
    target_org_id = uuid4()
    target_agent_id = uuid4()
    
    org = Organization(id=org_id, name="Org A", domain="orga.com", status="active")
    agent = Agent(id=agent_id, organization_id=org_id, name="Agent A", agent_type="Test", status="active")
    org_identity = OrganizationIdentity(id=uuid4(), organization_id=org_id, did="did:web:orga", public_key="fake", status="active")
    agent_identity = AgentIdentity(id=uuid4(), agent_id=agent_id, did="did:web:agenta", public_key="fake", status="active")
    
    target_org = Organization(id=target_org_id, name="Org B", domain="orgb.com", status="active")
    target_agent = Agent(id=target_agent_id, organization_id=target_org_id, name="Agent B", agent_type="Test", status="active")
    target_agent_identity = AgentIdentity(id=uuid4(), agent_id=target_agent_id, did="did:web:agentb", public_key="fake", status="active")
    
    pub_bytes = private_key_mock.public_key().public_bytes_raw()
    pub_b64 = base64.b64encode(pub_bytes).decode("ascii")
    
    org_identity.public_key = pub_b64
    
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=org_identity.id,
        verification_method=f"{org_identity.did}#key-1",
        public_key=pub_b64,
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        status="active"
    )
    
    db.add_all([org, agent, org_identity, agent_identity, target_org, target_agent, target_agent_identity, key])
    db.commit()
    
    return {
        "org_id": org_id,
        "agent_id": agent_id,
        "target_agent_did": "did:web:agentb",
        "agent_identity": agent_identity,
    }

@pytest.mark.asyncio
async def test_orchestrator_with_valid_delegation(db, test_data, monkeypatch):
    from app.services.action_orchestrator_service import verify_vp_and_consume_challenge
    import app.services.action_orchestrator_service as aos
    monkeypatch.setattr(aos, "verify_vp_and_consume_challenge", MagicMock(return_value=test_data["agent_identity"]))
    
    # Create valid delegation using real service logic
    principal = Principal(organization_id=test_data["org_id"], subject="test")
    del_create = DelegationCreate(
        delegator_organization_id=test_data["org_id"],
        delegatee_agent_id=test_data["agent_id"],
        purpose="Testing",
        starts_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        capabilities=[DelegationCapabilityCreate(capability_code="credential.issue", scope={}, constraints={})]
    )
    delegation = await create_delegation(db, principal, del_create)
    db.commit()
    
    result = await ActionOrchestratorService.execute_action(
        db=db,
        challenge_id=uuid4(),
        vp_jwt="fake",
        target_agent_did=test_data["target_agent_did"],
        action_type="verifiable_credential.issue",
        resource_id="cred-1",
        payload={},
        delegation_id=delegation.id
    )
    assert result["status"] == "SUCCESS"

@pytest.mark.asyncio
async def test_orchestrator_missing_delegation(db, test_data, monkeypatch):
    import app.services.action_orchestrator_service as aos
    monkeypatch.setattr(aos, "verify_vp_and_consume_challenge", MagicMock(return_value=test_data["agent_identity"]))
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await ActionOrchestratorService.execute_action(
            db=db,
            challenge_id=uuid4(),
            vp_jwt="fake",
            target_agent_did=test_data["target_agent_did"],
            action_type="verifiable_credential.issue",
            resource_id="cred-1",
            payload={},
            delegation_id=None
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["reason"] in ["DELEGATION_REQUIRED", "DELEGATION_INVALID", "CAPABILITY_NOT_FOUND"]
    
@pytest.mark.asyncio
async def test_orchestrator_invalid_delegation(db, test_data, monkeypatch):
    import app.services.action_orchestrator_service as aos
    monkeypatch.setattr(aos, "verify_vp_and_consume_challenge", MagicMock(return_value=test_data["agent_identity"]))
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await ActionOrchestratorService.execute_action(
            db=db,
            challenge_id=uuid4(),
            vp_jwt="fake",
            target_agent_did=test_data["target_agent_did"],
            action_type="verifiable_credential.issue",
            resource_id="cred-1",
            payload={},
            delegation_id=uuid4() # completely fake/missing uuid
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["reason"] in ["DELEGATION_REQUIRED", "DELEGATION_INVALID", "CAPABILITY_NOT_FOUND"]

@pytest.mark.asyncio
async def test_orchestrator_wrong_capability(db, test_data, monkeypatch):
    import app.services.action_orchestrator_service as aos
    monkeypatch.setattr(aos, "verify_vp_and_consume_challenge", MagicMock(return_value=test_data["agent_identity"]))
    
    principal = Principal(organization_id=test_data["org_id"], subject="test")
    del_create = DelegationCreate(
        delegator_organization_id=test_data["org_id"],
        delegatee_agent_id=test_data["agent_id"],
        purpose="Testing",
        starts_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        capabilities=[DelegationCapabilityCreate(capability_code="agent.read", scope={}, constraints={})]
    )
    delegation = await create_delegation(db, principal, del_create)
    db.commit()
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await ActionOrchestratorService.execute_action(
            db=db,
            challenge_id=uuid4(),
            vp_jwt="fake",
            target_agent_did=test_data["target_agent_did"],
            action_type="verifiable_credential.issue",
            resource_id="cred-1",
            payload={},
            delegation_id=delegation.id
        )
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["reason"] == "CAPABILITY_DENIED"

