import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status
from fastapi.testclient import TestClient
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.delegation import Delegation
from app.models.agent_template_decision import AgentTemplateDecision
from app.models.organization import Organization
from app.database.connection import get_db
from app.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import Base

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def override_get_db():
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _override
    yield _override
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def client(override_get_db):
    from fastapi.testclient import TestClient
    return TestClient(app)

from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64
from datetime import datetime, timezone, timedelta

def generate_ed25519_keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return private_key, base64.b64encode(pub_bytes).decode('utf-8')

@pytest.fixture
def test_setup(override_get_db, monkeypatch):
    db = next(override_get_db())
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    
    org = Organization(name="Test Org", domain=f"test-{uuid4()}.org")
    db.add(org)
    db.commit()
    
    org_did = f"did:web:test.org:{org.id}"
    org_priv, org_pub = generate_ed25519_keypair()

    org_ident = OrganizationIdentity(organization_id=org.id, did=org_did, public_key=org_pub)
    db.add(org_ident)
    db.commit()

    org_key = OrganizationIdentityKey(
        organization_identity_id=org_ident.id,
        verification_method=f"{org_did}#key-1",
        public_key=org_pub,
        valid_from=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db.add(org_key)
    db.commit()

    from app.services.organization_key_service import save_private_key
    save_private_key(org.id, org_priv)
    
    return {
        "db": db,
        "organization_id": org.id,
        "org_did": org_did,
        "org_priv": org_priv
    }

# Ensure authentication works by mocking get_current_principal
from app.api.dependencies import Principal, get_current_principal
@pytest.fixture(autouse=True)
def mock_principal(test_setup):
    def _override():
        return Principal(subject=f"did:web:test.org", organization_id=test_setup["organization_id"])
    app.dependency_overrides[get_current_principal] = _override
    yield
    app.dependency_overrides.pop(get_current_principal, None)

@pytest.mark.asyncio
def test_legacy_agent_registration(client: TestClient, test_setup: dict):
    # Test existing generic agent creation
    org_id = test_setup["organization_id"]
    
    response = client.post(
        "/agents",
        json={
            "organization_id": str(org_id),
            "name": "Legacy Agent",
            "agent_type": "generic",
            "description": "Legacy agent without template"
        }
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Legacy Agent"
    assert data["template_id"] is None
    assert data["template_version"] is None


@pytest.mark.asyncio
def test_template_registration_success(client: TestClient, test_setup: dict):
    org_id = test_setup["organization_id"]
    
    response = client.post(
        "/agents/register-template",
        json={
            "organization_id": str(org_id),
            "name": "HR Domain Agent",
            "template_id": "hr_agent",
            "template_version": "1.0.0",
            "capabilities": {
                "hr.read_policies": "ALLOWED",
                "hr.calculate_leave_balance": "DENIED"
            }
        }
    )
    
    if response.status_code != status.HTTP_201_CREATED:
        print(f"Failed with 400: {response.json()}")

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["template_id"] == "hr_agent"
    assert data["template_version"] == "1.0.0"
    
    agent_id = UUID(data["id"])
    
    # Check DB directly
    db = test_setup["db"]
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    assert agent is not None
    
    # Check Identity created
    identity = db.query(AgentIdentity).filter(AgentIdentity.agent_id == agent_id).first()
    assert identity is not None
    
    # Check decisions
    decisions = db.query(AgentTemplateDecision).filter(AgentTemplateDecision.agent_id == agent_id).all()
    assert len(decisions) == 2
    decision_map = {d.capability_code: d.decision for d in decisions}
    assert decision_map["hr.read_policies"] == "ALLOWED"
    assert decision_map["hr.calculate_leave_balance"] == "DENIED"
    
    # Check delegation
    delegations = db.query(Delegation).filter(Delegation.delegatee_agent_id == agent_id).all()
    assert len(delegations) == 1
    delegation = delegations[0]
    
    # Ensure only ALLOWED capabilities were delegated
    delegation_caps = [c.capability_code for c in delegation.capabilities]
    assert "hr.read_policies" in delegation_caps
    assert "hr.calculate_leave_balance" not in delegation_caps


@pytest.mark.asyncio
def test_template_registration_unauthorized(client: TestClient, test_setup: dict):
    # Use an org id different from the principal's
    wrong_org_id = uuid4()
    
    response = client.post(
        "/agents/register-template",
        json={
            "organization_id": str(wrong_org_id),
            "name": "HR Domain Agent",
            "template_id": "hr_agent",
            "template_version": "1.0.0",
            "capabilities": {}
        }
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
def test_template_registration_unsupported_capability(client: TestClient, test_setup: dict):
    org_id = test_setup["organization_id"]
    
    response = client.post(
        "/agents/register-template",
        json={
            "organization_id": str(org_id),
            "name": "HR Domain Agent",
            "template_id": "hr_agent",
            "template_version": "1.0.0",
            "capabilities": {
                "hr.read_policies": "ALLOWED",
                "hr.delete_employee": "ALLOWED"  # Unsupported!
            }
        }
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported capability" in response.json()["detail"]


@pytest.mark.asyncio
def test_template_registration_unknown_template(client: TestClient, test_setup: dict):
    org_id = test_setup["organization_id"]
    
    response = client.post(
        "/agents/register-template",
        json={
            "organization_id": str(org_id),
            "name": "Unknown Agent",
            "template_id": "unknown_agent",
            "template_version": "1.0.0",
            "capabilities": {}
        }
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unknown template" in response.json()["detail"]
