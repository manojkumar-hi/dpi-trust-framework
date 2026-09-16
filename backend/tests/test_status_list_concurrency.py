import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.orm import Session
from app.models.verifiable_credential import VerifiableCredential
from app.models.bitstring_status_list import BitstringStatusList
from app.services.status_list_service import _decode_bitstring, _get_bit
import jwt
from uuid import uuid4

# Do NOT import from test_status_list_fixtures

@pytest.mark.asyncio
async def test_concurrent_revocations_on_same_status_list():
    from app.main import app
    from app.database.connection import SessionLocal
    from app.models.organization import Organization
    from app.models.agent import Agent
    from app.models.organization_identity import OrganizationIdentity
    from app.models.organization_identity_key import OrganizationIdentityKey
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
    from app.services.organization_key_service import save_private_key
    
    db = SessionLocal()
    org_id = uuid4()
    org = Organization(id=org_id, name="Test", domain=f"test-{org_id}", status="active")
    db.add(org)
    
    agent_id = uuid4()
    agent = Agent(id=agent_id, organization_id=org_id, name="Test Agent", agent_type="system", status="active")
    db.add(agent)
    
    
    
    # Org identity
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    org_identity = OrganizationIdentity(
        id=uuid4(),
        organization_id=org_id,
        did=f"did:web:test:{org_id}",
        public_key=public_key_bytes
    )
    db.add(org_identity)
    
    from app.models.agent_identity import AgentIdentity
    agent_identity = AgentIdentity(
        id=uuid4(),
        agent_id=agent_id,
        did=f"did:web:test:{org_id}:agent",
        public_key=private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    )
    db.add(agent_identity)
    
    from datetime import datetime, timezone, timedelta
    db.add(OrganizationIdentityKey(
        organization_identity_id=org_identity.id,
        verification_method=f"{org_identity.did}#key-1",
        public_key=public_key_bytes,
        status="active",
        valid_from=datetime.now(timezone.utc) - timedelta(seconds=1)
    ))
    db.commit()
    
    save_private_key(org_id, private_key)
    
    from fastapi.testclient import TestClient
    sync_client = TestClient(app)

    cred_data = {
        "issuer_organization_id": str(org_id),
        "subject_agent_id": str(agent_id),
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "test"}
    }

    headers = {"X-Mock-Principal-Org-Id": str(org_id)}
    
    # Let's mock auth so we don't need real token
    from app.api.dependencies import get_current_principal, Principal
    from fastapi import Request
    def mock_get_principal(request: Request):
        import uuid
        org_id = request.headers.get("X-Mock-Principal-Org-Id")
        if org_id:
            return Principal(organization_id=uuid.UUID(org_id), subject="mock|mock")
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthenticated")
        
    app.dependency_overrides[get_current_principal] = mock_get_principal

    res1 = sync_client.post("/credentials", json=cred_data, headers=headers)
    assert res1.status_code == 201, res1.text
    res2 = sync_client.post("/credentials", json=cred_data, headers=headers)
    assert res2.status_code == 201, res2.text

    cred1_id = res1.json()["id"]
    cred2_id = res2.json()["id"]
    
    # Ensure they use same status list but different indexes
    payload1 = jwt.decode(res1.json()["vc_jwt"], options={"verify_signature": False})
    payload2 = jwt.decode(res2.json()["vc_jwt"], options={"verify_signature": False})
    
    assert payload1["vc"]["credentialStatus"]["statusListCredential"] == payload2["vc"]["credentialStatus"]["statusListCredential"]
    idx1 = int(payload1["vc"]["credentialStatus"]["statusListIndex"])
    idx2 = int(payload2["vc"]["credentialStatus"]["statusListIndex"])
    assert idx1 != idx2
    
    from httpx import ASGITransport
    # Revoke them concurrently
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"X-Mock-Principal-Org-Id": str(org_id)}
        
        # Fire both revocations concurrently
        task1 = ac.post(f"/credentials/{cred1_id}/revoke", headers=headers, json={"reason": "test"})
        task2 = ac.post(f"/credentials/{cred2_id}/revoke", headers=headers, json={"reason": "test"})
        
        responses = await asyncio.gather(task1, task2)
        assert responses[0].status_code == 200
        assert responses[1].status_code == 200

    # Both should be revoked
    # Download the status list
    list_id = payload1["vc"]["credentialStatus"]["statusListCredential"].split("/")[-1]
    list_res = sync_client.get(f"/.well-known/status-lists/{list_id}")
    sl_jwt = list_res.text
    
    sl_payload = jwt.decode(sl_jwt, options={"verify_signature": False})
    encoded_list = sl_payload["vc"]["credentialSubject"]["encodedList"]
    bitstring = _decode_bitstring(encoded_list)
    
    # Both bits must be set
    assert _get_bit(bitstring, idx1) is True
    assert _get_bit(bitstring, idx2) is True
