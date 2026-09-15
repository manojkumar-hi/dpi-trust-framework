import pytest
import jwt
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import math

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.agent_identity import AgentIdentity
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from app.services.organization_key_service import save_private_key

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
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

from app.api.dependencies import get_current_principal, Principal
from fastapi import Request, HTTPException
from uuid import UUID

def mock_get_principal(request: Request):
    org_id = request.headers.get("X-Mock-Principal-Org-Id")
    if org_id:
        return Principal(organization_id=UUID(org_id), subject="mock|mock")
    raise HTTPException(status_code=401, detail="Unauthenticated: Principal required")

@pytest.fixture(autouse=True)
def setup_app_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_principal] = mock_get_principal
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_principal, None)

client = TestClient(app)

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
    
    # Needs a key and identity
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
        agent_type="bot",
        status="active"
    )
    setup_db.add(agent)
    
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    import base64
    pub_b64 = base64.b64encode(pub.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    
    ident = AgentIdentity(
        id=uuid4(),
        agent_id=agent.id,
        did=f"did:web:test.org:agents:{agent.id}",
        public_key=pub_b64,
        key_algorithm="Ed25519",
        status="active"
    )
    setup_db.add(ident)
    setup_db.commit()
    setup_db.refresh(agent)
    return agent

def test_vc_jwt_issuance(setup_db, test_organization, test_agent):
    # Issue credential
    credential_data = {
        "issuer_organization_id": str(test_organization.id),
        "subject_agent_id": str(test_agent.id),
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "test_agent"},
    }
    response = client.post(
        "/credentials",
        json=credential_data,
        headers={"X-Mock-Principal-Org-Id": str(test_organization.id)},
    )
    
    # Debug print if it fails
    if response.status_code != 201:
        print("Failed to issue credential:", response.json())
        
    assert response.status_code == 201
    data = response.json()
    assert data["vc_jwt"] is not None
    assert data["kid"] is not None
    
    # Parse unverified headers
    vc_jwt = data["vc_jwt"]
    unverified_header = jwt.get_unverified_header(vc_jwt)
    assert "kid" in unverified_header
    assert unverified_header["kid"] == data["kid"]
    assert unverified_header["alg"] == "EdDSA"
    
    # Check payload
    unverified_payload = jwt.decode(vc_jwt, options={"verify_signature": False})
    assert unverified_payload["iss"] == f"did:web:test.org"
    assert unverified_payload["sub"] == f"did:web:test.org:agents:{test_agent.id}"
    assert unverified_payload["jti"] == data["id"]
    
    vc = unverified_payload["vc"]
    assert vc["@context"] == ["https://www.w3.org/2018/credentials/v1"]
    assert vc["type"] == ["VerifiableCredential", "DPIAgentCredential"]
    assert vc["credentialSubject"]["id"] == unverified_payload["sub"]
    assert vc["credentialSubject"]["role"] == "test_agent"
    
    # Verify via API
    verify_response = client.get(
        f"/credentials/{data['id']}/verify",
        headers={"X-Mock-Principal-Org-Id": str(test_organization.id)},
    )
    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    if not verify_data["valid"]:
        print("Verification failed:", verify_data["verification_message"])
        print("Signature status:", verify_data["signature_status"])
    assert verify_data["valid"] is True
    assert verify_data["cryptographically_verified"] is True
    assert verify_data["signature_status"] == "valid"
    assert verify_data["vc_jwt"] == vc_jwt
    assert verify_data["kid"] == data["kid"]
