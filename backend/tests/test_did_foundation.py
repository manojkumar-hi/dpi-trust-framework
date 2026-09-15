import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.base import Base
from app.database.connection import get_db
from app.models.organization import Organization
from app.models.agent import Agent
from app.services.identity_service import generate_did as generate_agent_did, create_identity as create_agent_identity
from app.services.organization_identity_service import generate_organization_did, create_organization_identity


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_app_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

def test_deterministic_organization_did_generation():
    domain = "trust.example.com"
    did = generate_organization_did(domain)
    assert did == "did:web:trust.example.com"

def test_deterministic_agent_did_generation():
    domain = "trust.example.com"
    agent_id = "123e4567-e89b-12d3-a456-426614174000"
    did = generate_agent_did(agent_id, domain)
    assert did == f"did:web:trust.example.com:agents:{agent_id}"

def test_did_web_endpoints(setup_db):
    db = setup_db
    
    org = Organization(id=uuid4(), name="Test Org", domain="test.org", status="active")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    create_organization_identity(db, org.id)
    
    agent = Agent(id=uuid4(), organization_id=org.id, name="Test Agent", agent_type="bot", status="active")
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    create_agent_identity(db, agent.id)

    domain = org.domain
    
    response = client.get("/.well-known/did.json", headers={"Host": domain})
    assert response.status_code == 200, response.json()
    doc = response.json()
    assert doc["id"] == f"did:web:{domain}"
    assert "verificationMethod" in doc
    assert "authentication" in doc
    assert "assertionMethod" in doc

    agent_response = client.get(f"/agents/{agent.id}/did.json", headers={"Host": domain})
    assert agent_response.status_code == 200, agent_response.json()
    agent_doc = agent_response.json()
    assert agent_doc["id"] == f"did:web:{domain}:agents:{agent.id}"
    assert "verificationMethod" in agent_doc
    assert "authentication" in agent_doc
    assert "assertionMethod" in agent_doc
