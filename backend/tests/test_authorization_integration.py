import math
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.main import app
from app.database.base import Base
from app.database.connection import get_db
from sqlalchemy import create_engine, StaticPool, event
from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
@compiles(JSONB, 'sqlite')
def compile_jsonb(type_, compiler, **kw):
    return "JSON"

from app.models.organization import Organization
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.delegation import Delegation
from tests.test_delegation_phase2 import _signed_delegation, _public_key

from app.services import delegation_service

original_verify = delegation_service.verify_delegation

async def patched_verify_delegation(db, delegation_id):
    delegation = db.get(Delegation, delegation_id)
    if delegation:
        for attr in ['starts_at', 'expires_at', 'signed_at', 'created_at', 'updated_at', 'revoked_at']:
            val = getattr(delegation, attr)
            if val and val.tzinfo is None:
                setattr(delegation, attr, val.replace(tzinfo=timezone.utc))
        
        # SQLite also loads keys naive
        keys = db.query(OrganizationIdentityKey).all()
        for k in keys:
            for attr in ['valid_from', 'valid_until']:
                val = getattr(k, attr)
                if val and val.tzinfo is None:
                    setattr(k, attr, val.replace(tzinfo=timezone.utc))
                    
    return await original_verify(db, delegation_id)

@pytest.fixture(autouse=True)
def patch_delegation_service(monkeypatch):
    import app.api.authorization_dependency
    monkeypatch.setattr(app.api.authorization_dependency, "verify_delegation", patched_verify_delegation)
    
    # Mock SessionLocal entirely to prevent SQLite in-memory deadlock
    from unittest.mock import MagicMock
    monkeypatch.setattr(app.api.authorization_dependency, "SessionLocal", MagicMock())

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

@pytest.fixture(autouse=True)
def setup_app_overrides():
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides = original_overrides

from app.api.dependencies import get_current_principal, Principal
from fastapi import Request
from uuid import UUID

def mock_get_principal(request: Request):
    org_id = request.headers.get("x-mock-principal-org-id")
    if org_id:
        return Principal(organization_id=UUID(org_id), subject="mock|mock")
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Unauthenticated: Principal required")

app.dependency_overrides[get_current_principal] = mock_get_principal
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def auth_fixtures(setup_db):
    private_key = Ed25519PrivateKey.generate()
    delegation, org, agent, org_id, agent_id = _signed_delegation(private_key)
    
    # 2. Add to DB
    setup_db.add(org)
    setup_db.add(agent)
    setup_db.add(org_id)
    setup_db.add(agent_id)
    setup_db.commit()

    # 3. Create active key for organization
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=org_id.id,
        verification_method=f"{org_id.did}#key-1",
        public_key=_public_key(private_key),
        status="active",
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
    )
    setup_db.add(key)
    setup_db.commit()

    return {
        "org": org,
        "agent": agent,
        "org_id": org_id,
        "agent_id": agent_id,
        "private_key": private_key,
        "delegation_proto": delegation
    }

def _create_delegation(db, f, caps):
    delegation = f["delegation_proto"]
    delegation.created_at = datetime.now(timezone.utc)
    delegation.updated_at = datetime.now(timezone.utc)
    # Re-apply capabilities cleanly
    delegation.capabilities.clear()
    from app.models.delegation_capability import DelegationCapability
    for c in caps:
        delegation.capabilities.append(DelegationCapability(capability_code=c, scope={}, constraints={}))
    
    # Re-sign with new capabilities
    from app.services.delegation_canonicalization import canonical_delegation_bytes, delegation_hash
    import base64
    payloads = [{"capabilityCode": c, "scope": {}, "constraints": {}} for c in caps]
    signed_bytes = canonical_delegation_bytes(
        delegation_id=delegation.id,
        delegator_did=delegation.delegator_did,
        delegatee_did=delegation.delegatee_did,
        parent_delegation_id=delegation.parent_delegation_id,
        root_delegation_id=delegation.root_delegation_id,
        depth=delegation.depth,
        purpose=delegation.purpose,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        issued_at=delegation.signed_at,
        capabilities=payloads,
    )
    delegation.signature = base64.b64encode(f["private_key"].sign(signed_bytes)).decode("ascii")
    delegation.canonical_hash = delegation_hash(
        delegation_id=delegation.id,
        delegator_did=delegation.delegator_did,
        delegatee_did=delegation.delegatee_did,
        parent_delegation_id=delegation.parent_delegation_id,
        root_delegation_id=delegation.root_delegation_id,
        depth=delegation.depth,
        purpose=delegation.purpose,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        issued_at=delegation.signed_at,
        capabilities=payloads,
    )

    db.add(delegation)
    db.commit()
    return delegation

def test_missing_delegation(auth_fixtures):
    f = auth_fixtures
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    
    # Send request without delegation_id
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "DELEGATION_INVALID"

def test_missing_capability(auth_fixtures, setup_db):
    f = auth_fixtures
    delegation = _create_delegation(setup_db, f, ["agent.read"]) # Missing dpi.auth.issue
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op?delegation_id={delegation.id}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "CAPABILITY_DENIED"

def test_invalid_revoked_delegation(auth_fixtures, setup_db):
    f = auth_fixtures
    delegation = _create_delegation(setup_db, f, ["credential.issue"])
    delegation.status = "revoked"
    delegation.revoked_at = datetime.now(timezone.utc)
    delegation.revocation_reason = "Test"
    setup_db.commit()
    
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op?delegation_id={delegation.id}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "DELEGATION_INVALID"

def test_insufficient_trust(auth_fixtures, setup_db):
    f = auth_fixtures
    delegation = _create_delegation(setup_db, f, ["credential.issue"])
    
    # Initial trust is 0.5 (below 0.8)
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op?delegation_id={delegation.id}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "UNCERTAINTY_TOO_HIGH"

def test_fully_authorized_request(auth_fixtures, setup_db):
    f = auth_fixtures
    delegation = _create_delegation(setup_db, f, ["credential.issue"])
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    
    # Push Trust above 0.8
    for _ in range(20):
        client.post(f"/agents/{f['agent'].id}/trust/evidence", json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0}, headers=headers)
    
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op?delegation_id={delegation.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["decision"]["reason_code"] == "AUTHORIZED"

def test_excessive_recent_risk(auth_fixtures, setup_db):
    f = auth_fixtures
    delegation = _create_delegation(setup_db, f, ["credential.issue"])
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    
    for _ in range(20):
        client.post(f"/agents/{f['agent'].id}/trust/evidence", json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0}, headers=headers)
        
    # Introduce critical risk (RR max is 0.1)
    client.post(f"/agents/{f['agent'].id}/trust/evidence", json={"outcome": "failure", "severity": 16, "evidence_quality": 1.0}, headers=headers)

    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op?delegation_id={delegation.id}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "RECENT_RISK_TOO_HIGH"

def test_invalid_identity(auth_fixtures, setup_db):
    f = auth_fixtures
    delegation = _create_delegation(setup_db, f, ["credential.issue"])
    
    f["agent_id"].status = "revoked"
    setup_db.commit()
    
    headers = {"X-Mock-Principal-Org-Id": str(f["org"].id)}
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op?delegation_id={delegation.id}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "IDENTITY_INVALID"

def test_unauthorized_organization_principal(auth_fixtures, setup_db):
    f = auth_fixtures
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}
    resp = client.post(f"/agents/{f['agent'].id}/simulated-sensitive-op", headers=headers)
    assert resp.status_code == 403
    assert "Principal not authorized" in resp.json()["detail"]
