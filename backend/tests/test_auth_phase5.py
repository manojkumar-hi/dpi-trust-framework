import pytest
import jwt
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.main import app
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity

from tests.test_auth import mock_jwks_response, rsa_public_key

from app.database.connection import get_db
from app.database.base import Base
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    saved_override = app.dependency_overrides.get(get_db)
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    
    yield db
    
    if saved_override:
        app.dependency_overrides[get_db] = saved_override
    else:
        app.dependency_overrides.pop(get_db, None)
    db.close()

client = TestClient(app)
from tests.test_auth import rsa_private_key

@pytest.fixture
def auth_setup(setup_db, monkeypatch):
    from app.main import app
    from app.api.dependencies import get_current_principal
    # Remove test mock so real auth is used, but save it
    saved_override = app.dependency_overrides.get(get_current_principal)
    if get_current_principal in app.dependency_overrides:
        app.dependency_overrides.pop(get_current_principal)

    # Setup test org
    org_id = uuid4()
    org = Organization(id=org_id, name="Phase 5 Org", domain="phase5.local", status="active")
    setup_db.add(org)
    
    # Setup identity
    ident = OrganizationIdentity(
        id=uuid4(),
        organization_id=org_id,
        did="did:web:phase5.local",
        public_key="mock-pub-key",
        authentication_issuer="https://auth.dpi-trust.local",
        authentication_subject="phase5-sub",
        key_algorithm="RS256",
        status="active"
    )
    setup_db.add(ident)
    setup_db.commit()
    
    # Setup HTTPX mock on the dependency instance
    mock_client = MagicMock()
    mock_client.get.return_value = mock_jwks_response(kid="test-kid")
    
    from app.api.dependencies import jwt_validator
    monkeypatch.setattr("app.api.dependencies.jwt_validator._http_client", mock_client)
    monkeypatch.setattr("app.api.dependencies.jwt_validator.settings.auth_jwks_url", "https://auth.dpi-trust.local/.well-known/jwks.json")
    monkeypatch.setattr("app.api.dependencies.jwt_validator.settings.auth_static_public_key", None)
    
    class MockSessionLocal:
        def __enter__(self):
            return setup_db
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    monkeypatch.setattr("app.api.dependencies.SessionLocal", MockSessionLocal)
    
    jwt_validator._jwks_cache.clear()
    jwt_validator._last_jwks_refresh = 0.0
    
    from app.models.agent import Agent
    agent = Agent(id=uuid4(), organization_id=org_id, name="Test Agent", agent_type="bot", status="ACTIVE")
    setup_db.add(agent)
    setup_db.commit()
    
    yield org_id, ident.id, agent.id

    # Restore the saved override
    if saved_override is not None:
        app.dependency_overrides[get_current_principal] = saved_override
    elif get_current_principal in app.dependency_overrides:
        app.dependency_overrides.pop(get_current_principal)

def test_mock_header_alone_rejected(setup_db: Session, auth_setup):
    org_id, ident_id, agent_id = auth_setup
    res = client.post(
        f"/agents/{agent_id}/simulated-sensitive-op",
        headers={"X-Mock-Principal-Org-Id": str(org_id)}
    )
    assert res.status_code == 401, res.json()
    assert res.json()["detail"] == "TOKEN_MISSING"

def test_missing_token_rejected(setup_db: Session, auth_setup):
    org_id, ident_id, agent_id = auth_setup
    res = client.post(f"/agents/{agent_id}/simulated-sensitive-op")
    assert res.status_code == 401, res.json()
    assert res.json()["detail"] == "TOKEN_MISSING"

def test_valid_jwt_and_success_audit(setup_db: Session, auth_setup):
    org_id, ident_id, agent_id = auth_setup
    payload = {"iss": "https://auth.dpi-trust.local", "aud": "dpi-trust-framework", "sub": "phase5-sub", "exp": 2000000000, "nbf": 0}
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256", headers={"kid": "test-kid"})
    
    res = client.post(f"/agents/{uuid4()}/simulated-sensitive-op", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code != 401, res.json()
    
    from app.models.audit_record import AuditRecord
    setup_db.commit()
    audit = setup_db.query(AuditRecord).filter(AuditRecord.event_type == "authentication_succeeded").order_by(AuditRecord.occurred_at.desc()).first()
    assert audit is not None
    assert audit.actor_organization_id == org_id
    assert audit.reason_code == "AUTHENTICATED"
    assert "token" not in str(audit.trust_snapshot).lower()

def test_invalid_signature_audit(setup_db: Session, auth_setup):
    payload = {"iss": "https://auth.dpi-trust.local", "aud": "dpi-trust-framework", "sub": "phase5-sub", "exp": 2000000000, "nbf": 0}
    # Sign with a different key
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    token = jwt.encode(payload, wrong_key, algorithm="RS256", headers={"kid": "test-kid"})
    
    res = client.post(f"/agents/{uuid4()}/simulated-sensitive-op", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "TOKEN_SIGNATURE_INVALID"

def test_expired_token(setup_db: Session, auth_setup):
    payload = {"iss": "https://auth.dpi-trust.local", "aud": "dpi-trust-framework", "sub": "phase5-sub", "exp": 1000, "nbf": 0}
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256", headers={"kid": "test-kid"})
    res = client.post(f"/agents/{uuid4()}/simulated-sensitive-op", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "TOKEN_EXPIRED"

def test_unknown_identity(setup_db: Session, auth_setup):
    payload = {"iss": "https://auth.dpi-trust.local", "aud": "dpi-trust-framework", "sub": "unknown", "exp": 2000000000, "nbf": 0}
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256", headers={"kid": "test-kid"})
    res = client.post(f"/agents/{uuid4()}/simulated-sensitive-op", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "IDENTITY_NOT_FOUND"
    
def test_conflicting_identity_hints(setup_db: Session, auth_setup):
    payload = {"iss": "https://auth.dpi-trust.local", "aud": "dpi-trust-framework", "sub": "phase5-sub", "dpi_org_id": str(uuid4()), "exp": 2000000000, "nbf": 0}
    token = jwt.encode(payload, rsa_private_key, algorithm="RS256", headers={"kid": "test-kid"})
    res = client.post(f"/agents/{uuid4()}/simulated-sensitive-op", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "IDENTITY_MISMATCH"
