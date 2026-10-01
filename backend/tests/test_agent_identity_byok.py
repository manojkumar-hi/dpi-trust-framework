import base64
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.base import Base
from app.database.connection import get_db
from app.models.organization import Organization
from app.models.agent import Agent
from app.api.dependencies import get_current_principal, Principal
from app.services.identity_service import get_identity_for_agent

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
    old_db = app.dependency_overrides.get(get_db)
    old_principal = app.dependency_overrides.get(get_current_principal)
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    if old_db:
        app.dependency_overrides[get_db] = old_db
    else:
        app.dependency_overrides.pop(get_db, None)
        
    if old_principal:
        app.dependency_overrides[get_current_principal] = old_principal
    else:
        app.dependency_overrides.pop(get_current_principal, None)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

def generate_key_pair():
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public_key_b64 = base64.b64encode(public_key_bytes).decode("ascii")
    return private_key, public_key_b64

def test_byok_create_and_rekey(setup_db):
    db = setup_db
    org_id = uuid4()
    org = Organization(id=org_id, name="Test Org", domain="test.org", status="active")
    db.add(org)
    
    agent_id = uuid4()
    agent = Agent(id=agent_id, organization_id=org_id, name="Test Agent", agent_type="bot", status="active")
    db.add(agent)
    db.commit()

    # Mock principal to match org
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        organization_id=org_id, scopes=[]
    )

    # 1. BYOK Create
    priv1, pub1_b64 = generate_key_pair()
    
    response = client.post(
        f"/agents/{agent_id}/identity",
        json={"public_key_b64": pub1_b64}
    )
    assert response.status_code == 201
    doc = response.json()
    assert doc["public_key"] == pub1_b64

    # Verify via DB
    identity = get_identity_for_agent(db, agent_id)
    assert identity.public_key == pub1_b64
    assert len(identity.keys) == 1
    assert identity.keys[0].public_key == pub1_b64
    assert identity.keys[0].status == "active"
    
    # 2. Invalid Base64
    response_err = client.post(
        f"/agents/{agent_id}/identity/rekey",
        json={"public_key_b64": "invalid-base64!"}
    )
    assert response_err.status_code == 400
    
    # 3. Invalid length key
    invalid_pub_bytes = base64.b64encode(b"too_short").decode("ascii")
    response_err2 = client.post(
        f"/agents/{agent_id}/identity/rekey",
        json={"public_key_b64": invalid_pub_bytes}
    )
    assert response_err2.status_code == 400

    # 4. BYOK Rekey
    priv2, pub2_b64 = generate_key_pair()
    response2 = client.post(
        f"/agents/{agent_id}/identity/rekey",
        json={"public_key_b64": pub2_b64}
    )
    assert response2.status_code == 200
    doc2 = response2.json()
    assert doc2["public_key"] == pub2_b64

    # Verify via DB
    db.refresh(identity)
    assert identity.public_key == pub2_b64
    assert len(identity.keys) == 2
    
    retired_key = next(k for k in identity.keys if k.verification_method.endswith("#key-1"))
    active_key = next(k for k in identity.keys if k.verification_method.endswith("#key-2"))
    
    assert retired_key.status == "retired"
    assert active_key.status == "active"
    assert active_key.public_key == pub2_b64
