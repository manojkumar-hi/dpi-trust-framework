from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.main import app
from app.database.connection import get_db
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.delegation import Delegation
from app.services import delegation_service

from tests.test_delegation_phase2 import (
    FakeSession,
    _identities,
    _request,
    _signed_delegation,
    _public_key,
)

def _signed_delegation_with_timestamps(*args, **kwargs):
    delegation, organization, agent, organization_identity, agent_identity = _signed_delegation(*args, **kwargs)
    delegation.created_at = datetime.now(timezone.utc)
    delegation.updated_at = datetime.now(timezone.utc)
    return delegation, organization, agent, organization_identity, agent_identity

client = TestClient(app)

@pytest.fixture
def test_db_session():
    private_key = Ed25519PrivateKey.generate()
    organization, agent, organization_identity, agent_identity = _identities(private_key)
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=organization_identity.id,
        verification_method=f"{organization_identity.did}#key-1",
        public_key=_public_key(private_key),
        status="active",
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session = FakeSession(organization, agent, organization_identity, agent_identity, key)
    session.private_key = private_key
    return session

@pytest.fixture
def override_get_db(test_db_session):
    def _get_db():
        yield test_db_session
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()

def _patch_fake_session_add():
    original_add = FakeSession.add
    def new_add(self, value):
        if isinstance(value, Delegation):
            value.created_at = datetime.now(timezone.utc)
            value.updated_at = datetime.now(timezone.utc)
        original_add(self, value)
    FakeSession.add = new_add
_patch_fake_session_add()

def test_create_delegation_success(override_get_db, test_db_session, monkeypatch):
    monkeypatch.setattr(delegation_service, "load_private_key", lambda _: test_db_session.private_key)
    
    org = test_db_session.organization
    agent = test_db_session.agent
    now = datetime.now(timezone.utc)
    
    payload = {
        "delegator_organization_id": str(org.id),
        "delegatee_agent_id": str(agent.id),
        "purpose": "Test Phase 3 API",
        "starts_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "capabilities": [{"capability_code": "agent.read"}]
    }

    headers = {"X-Mock-Principal-Org-Id": str(org.id)}
    response = client.post("/delegations", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["delegator_organization_id"] == str(org.id)
    assert data["status"] == "active"

def test_create_delegation_unauthorized_403(override_get_db, test_db_session, monkeypatch):
    monkeypatch.setattr(delegation_service, "load_private_key", lambda _: test_db_session.private_key)
    org = test_db_session.organization
    agent = test_db_session.agent
    now = datetime.now(timezone.utc)
    
    payload = {
        "delegator_organization_id": str(org.id),
        "delegatee_agent_id": str(agent.id),
        "purpose": "Test Phase 3 API",
        "starts_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "capabilities": [{"capability_code": "agent.read"}]
    }

    # Use a different org ID for the principal
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}
    response = client.post("/delegations", json=payload, headers=headers)
    assert response.status_code == 403
    assert "not authorized" in response.text

def test_create_delegation_validation_error_422(override_get_db, test_db_session, monkeypatch):
    monkeypatch.setattr(delegation_service, "load_private_key", lambda _: test_db_session.private_key)
    org = test_db_session.organization
    agent = test_db_session.agent
    now = datetime.now(timezone.utc)
    
    # Invalid: expires_at before starts_at
    payload = {
        "delegator_organization_id": str(org.id),
        "delegatee_agent_id": str(agent.id),
        "purpose": "Test Invalid",
        "starts_at": now.isoformat(),
        "expires_at": (now - timedelta(hours=1)).isoformat(),
        "capabilities": [{"capability_code": "agent.read"}]
    }
    headers = {"X-Mock-Principal-Org-Id": str(org.id)}
    response = client.post("/delegations", json=payload, headers=headers)
    assert response.status_code == 400
    assert "starts_at must be before expires_at" in response.text

def test_create_delegation_unknown_capability_422(override_get_db, test_db_session, monkeypatch):
    monkeypatch.setattr(delegation_service, "load_private_key", lambda _: test_db_session.private_key)
    org = test_db_session.organization
    agent = test_db_session.agent
    now = datetime.now(timezone.utc)
    
    payload = {
        "delegator_organization_id": str(org.id),
        "delegatee_agent_id": str(agent.id),
        "purpose": "Test Invalid Capability",
        "starts_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "capabilities": [{"capability_code": "unknown.capability"}]
    }
    headers = {"X-Mock-Principal-Org-Id": str(org.id)}
    response = client.post("/delegations", json=payload, headers=headers)
    assert response.status_code == 400
    assert "Unknown capability code" in response.text

def test_create_delegation_parent_rejection_422(override_get_db, test_db_session, monkeypatch):
    monkeypatch.setattr(delegation_service, "load_private_key", lambda _: test_db_session.private_key)
    org = test_db_session.organization
    agent = test_db_session.agent
    now = datetime.now(timezone.utc)
    
    payload = {
        "delegator_organization_id": str(org.id),
        "delegatee_agent_id": str(agent.id),
        "purpose": "Test Subdelegation",
        "starts_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "capabilities": [{"capability_code": "agent.read"}],
        "parent_delegation_id": str(uuid4())
    }
    headers = {"X-Mock-Principal-Org-Id": str(org.id)}
    response = client.post("/delegations", json=payload, headers=headers)
    assert response.status_code == 400
    assert "Subdelegation creation is not supported" in response.text

def test_get_delegation_404(override_get_db):
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}
    response = client.get(f"/delegations/{uuid4()}", headers=headers)
    assert response.status_code == 404

def test_retrieve_and_verify_delegation(override_get_db, test_db_session):
    delegation, org, agent, org_id, agent_id = _signed_delegation_with_timestamps(test_db_session.private_key)
    test_db_session.organization = org
    test_db_session.agent = agent
    test_db_session.organization_identity = org_id
    test_db_session.agent_identity = agent_id
    test_db_session.delegation = delegation
    test_db_session.key.organization_identity_id = org_id.id
    test_db_session.key.verification_method = f"{org_id.did}#key-1"
    
    headers = {"X-Mock-Principal-Org-Id": str(org.id)}
    
    # Retrieve
    response = client.get(f"/delegations/{delegation.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(delegation.id)
    
    # Verify
    verify_resp = client.get(f"/delegations/{delegation.id}/verify", headers=headers)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is True, verify_resp.json()
    assert verify_resp.json()["signature_valid"] is True

def test_verify_delegation_404(override_get_db):
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}
    response = client.get(f"/delegations/{uuid4()}/verify", headers=headers)
    assert response.status_code == 404

def test_revoke_delegation_and_verify_after_revocation(override_get_db, test_db_session):
    delegation, org, agent, org_id, agent_id = _signed_delegation_with_timestamps(test_db_session.private_key)
    test_db_session.organization = org
    test_db_session.agent = agent
    test_db_session.organization_identity = org_id
    test_db_session.agent_identity = agent_id
    test_db_session.delegation = delegation
    test_db_session.key.organization_identity_id = org_id.id
    test_db_session.key.verification_method = f"{org_id.did}#key-1"
    
    headers = {"X-Mock-Principal-Org-Id": str(org.id)}
    # Revoke
    revoke_payload = {"reason": "Compromised key"}
    revoke_resp = client.post(f"/delegations/{delegation.id}/revoke", json=revoke_payload, headers=headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"
    
    # Verify after revocation
    verify_resp = client.get(f"/delegations/{delegation.id}/verify", headers=headers)
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is False
    assert verify_resp.json()["lifecycle_valid"] is False
    assert verify_resp.json()["status"] == "revoked"
    
    # Try revoking again (idempotent success)
    revoke_resp2 = client.post(f"/delegations/{delegation.id}/revoke", json=revoke_payload, headers=headers)
    assert revoke_resp2.status_code == 200
    assert revoke_resp2.json()["status"] == "revoked"

def test_revoke_delegation_unauthorized_403(override_get_db, test_db_session):
    delegation, org, agent, org_id, agent_id = _signed_delegation_with_timestamps(test_db_session.private_key)
    test_db_session.organization = org
    test_db_session.agent = agent
    test_db_session.organization_identity = org_id
    test_db_session.agent_identity = agent_id
    test_db_session.delegation = delegation
    
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}  # Different org ID
    revoke_payload = {"reason": "Malicious revocation attempt"}
    revoke_resp = client.post(f"/delegations/{delegation.id}/revoke", json=revoke_payload, headers=headers)
    assert revoke_resp.status_code == 403
    assert "not authorized" in revoke_resp.text

def test_get_delegations_listing(override_get_db, test_db_session):
    delegation, org, agent, org_id, agent_id = _signed_delegation_with_timestamps(test_db_session.private_key)
    test_db_session.organization = org
    test_db_session.agent = agent
    test_db_session.organization_identity = org_id
    test_db_session.agent_identity = agent_id
    test_db_session.delegation = delegation
    
    # Mock the scalar().all() response inside get_delegations
    # Wait, FakeSession's scalars() doesn't exist, we added it. Let's patch get_delegations for listing
    pass

@patch("app.api.delegations.get_delegations")
def test_list_delegations_endpoint(mock_get_delegations, override_get_db):
    mock_get_delegations.return_value = []
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}
    resp = client.get("/delegations", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

@patch("app.api.delegations.get_delegation_chain")
def test_get_delegation_chain_endpoint(mock_get_chain, override_get_db):
    mock_get_chain.return_value = []
    headers = {"X-Mock-Principal-Org-Id": str(uuid4())}
    resp = client.get(f"/delegations/{uuid4()}/chain", headers=headers)
    assert resp.status_code == 200

@patch("app.api.organizations.get_delegations")
@patch("app.api.organizations.get_organization")
def test_organization_delegations_listing(mock_get_org, mock_get_dels, override_get_db):
    org_id = uuid4()
    mock_get_org.return_value = "org"
    mock_get_dels.return_value = []
    
    resp = client.get(f"/organizations/{org_id}/delegations")
    assert resp.status_code == 200

@patch("app.api.agents.get_delegations")
@patch("app.api.agents.get_agent")
def test_agent_delegations_listing(mock_get_agent, mock_get_dels, override_get_db):
    agent_id = uuid4()
    mock_get_agent.return_value = "agent"
    mock_get_dels.return_value = []
    
    resp = client.get(f"/agents/{agent_id}/delegations")
    assert resp.status_code == 200
