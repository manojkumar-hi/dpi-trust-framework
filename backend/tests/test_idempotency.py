import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime, timezone

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_idempotency_credentials():
    # 1. Setup organization and agent
    org_resp = client.post("/organizations", json={"name": "Idempotency Org", "domain": f"idem-{uuid4()}.example.com"})
    assert org_resp.status_code == 201
    org_id = org_resp.json()["id"]

    agent_resp = client.post("/agents", json={"organization_id": org_id, "name": "Idempotency Agent", "agent_type": "standard"})
    # wait, /agents is now protected! We need to override authentication.
    
    from app.api.dependencies import get_current_principal, Principal
    from uuid import UUID
    
    def mock_get_principal():
        return Principal(subject="did:web:example", organization_id=UUID(org_id), agent_id=None)
    
    app.dependency_overrides[get_current_principal] = mock_get_principal
    
    from unittest.mock import AsyncMock, patch
    mock_fabric = AsyncMock()
    mock_fabric.issue_credential.return_value = {"success": True}
    
    with patch("app.services.credential_service.FabricLedgerClient", return_value=mock_fabric):
        # Create org identity
        client.post(f"/organizations/{org_id}/identity")

        agent_resp = client.post("/agents", json={"organization_id": org_id, "name": "Idempotency Agent", "agent_type": "standard"})
        assert agent_resp.status_code == 201
        agent_id = agent_resp.json()["id"]

        # Create agent identity
        client.post(f"/agents/{agent_id}/identity")

        # Request payload
        payload = {
            "issuer_organization_id": org_id,
            "subject_agent_id": agent_id,
            "credential_type": "TestCredential",
            "credential_data": {"level": 1}
        }

        idem_key = f"idem-{uuid4()}"

        # 1. First request succeeds
        response1 = client.post(
            "/credentials",
            json=payload,
            headers={"Idempotency-Key": idem_key}
        )
        assert response1.status_code == 201
        cred_id = response1.json()["id"]

        # 2. Identical retry returns exactly original result
        response2 = client.post(
            "/credentials",
            json=payload,
            headers={"Idempotency-Key": idem_key}
        )
        assert response2.status_code == 201
        assert response2.json()["id"] == cred_id

        # 3. Same key + different payload -> 409
        payload_diff = {**payload, "credential_data": {"level": 2}}
        response3 = client.post(
            "/credentials",
            json=payload_diff,
            headers={"Idempotency-Key": idem_key}
        )
        assert response3.status_code == 409
        assert "different payload" in response3.json()["detail"]

        # 4. Different key -> independent operation
        idem_key2 = f"idem-{uuid4()}"
        response4 = client.post(
            "/credentials",
            json=payload,
            headers={"Idempotency-Key": idem_key2}
        )
        assert response4.status_code == 201
        assert response4.json()["id"] != cred_id

    # Clean up
    app.dependency_overrides.clear()


def test_idempotency_concurrent():
    from app.services.idempotency_service import IdempotencyService
    
    finger1 = IdempotencyService.fingerprint_request("/path", {"a": 1, "b": 2})
    finger2 = IdempotencyService.fingerprint_request("/path", {"b": 2, "a": 1})
    assert finger1 == finger2



