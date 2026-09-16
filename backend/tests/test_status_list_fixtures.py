import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.agent_identity import AgentIdentity
from app.services.organization_key_service import save_private_key
from app.api.dependencies import get_current_principal, Principal
from fastapi import Request, HTTPException

@compiles(JSONB, 'sqlite')
def compile_jsonb(type_, compiler, **kw):
    return "JSON"

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def mock_get_principal(request: Request):
    from uuid import UUID
    org_id = request.headers.get("X-Mock-Principal-Org-Id")
    if org_id:
        return Principal(organization_id=UUID(org_id), subject="mock|mock")
    raise HTTPException(status_code=401, detail="Unauthenticated")

@pytest.fixture(autouse=True)
def setup_app_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_principal] = mock_get_principal
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_principal, None)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def test_organization(setup_db):
    org = Organization(id=uuid4(), name="Test Org", domain="test.org", status="active")
    setup_db.add(org)
    
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    import base64
    pub_b64 = base64.b64encode(pub.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    
    ident = OrganizationIdentity(
        id=uuid4(),
        organization_id=org.id,
        did="did:web:test.org",
        public_key=pub_b64,
        key_algorithm="Ed25519",
        status="active"
    )
    setup_db.add(ident)
    
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=ident.id,
        verification_method="did:web:test.org#key-1",
        public_key=pub_b64,
        key_algorithm="Ed25519",
        status="active",
        valid_from=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    setup_db.add(key)
    setup_db.commit()
    
    save_private_key(org.id, priv)
    return org

@pytest.fixture
def test_agent(setup_db, test_organization):
    agent = Agent(
        id=uuid4(),
        organization_id=test_organization.id,
        name="Test Agent",
        agent_type="system",
        status="active"
    )
    setup_db.add(agent)
    
    ident = AgentIdentity(
        id=uuid4(),
        agent_id=agent.id,
        did="did:web:test.org:agent",
        public_key="test",
        key_algorithm="Ed25519",
        status="active"
    )
    setup_db.add(ident)
    setup_db.commit()
    return agent
