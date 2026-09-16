import pytest
import asyncio
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import base64
import jwt
import socket
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.main import app
from app.services.status_list_service import _STATUS_LIST_CACHE, StatusListError, _decode_bitstring, _get_bit, verify_and_check_status
from app.models.bitstring_status_list import BitstringStatusList
from app.services.credential_service import create_credential, revoke_credential, verify_credential
from app.models.verifiable_credential import VerifiableCredential
from app.api.credentials import revoke_credential_record
from app.services.idempotency_service import IdempotencyService
from app.models.idempotency import IdempotencyRecord
import app.utils.http_client as http_client

from tests.test_status_list_fixtures import *

client = TestClient(app)

@pytest.fixture
def clear_cache():
    _STATUS_LIST_CACHE.clear()
    yield
    _STATUS_LIST_CACHE.clear()

def test_public_api_endpoint(setup_app_overrides, setup_db, test_organization, test_agent):
    # Issue a credential to allocate a status list
    cred_data = {
        "issuer_organization_id": str(test_organization.id),
        "subject_agent_id": str(test_agent.id),
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "test"}
    }
    res = client.post("/credentials", json=cred_data, headers={"X-Mock-Principal-Org-Id": str(test_organization.id)})
    if res.status_code != 201:
        print(f"FAILED POST CREDENTIALS: {res.status_code} {res.json()}")
    assert res.status_code == 201
    vc_jwt = res.json()["vc_jwt"]
    
    # decode vc
    payload = jwt.decode(vc_jwt, options={"verify_signature": False})
    status_url = payload["vc"]["credentialStatus"]["statusListCredential"]
    list_id = status_url.split("/")[-1]
    
    # fetch list
    list_res = client.get(f"/.well-known/status-lists/{list_id}")
    assert list_res.status_code == 200
    assert list_res.headers["content-type"] == "application/vc+jwt"
    assert "public, max-age=300" in list_res.headers["cache-control"]
    
    # decode status list
    sl_jwt = list_res.text
    sl_payload = jwt.decode(sl_jwt, options={"verify_signature": False})
    assert sl_payload["vc"]["type"] == ["VerifiableCredential", "BitstringStatusListCredential"]

def test_cache_tampering(setup_app_overrides, setup_db, test_organization, test_agent, clear_cache, monkeypatch):
    # Mock HTTP fetch to use TestClient
    def mock_fetch(url):
        list_id = url.split("/")[-1]
        res = client.get(f"/.well-known/status-lists/{list_id}")
        if res.status_code == 200:
            return res.content
        raise Exception("Not found")
    import app.services.status_list_service as sl_service
    monkeypatch.setattr(sl_service, "fetch_status_list_artifact", mock_fetch)
    
    # Issue credential
    cred_data = {
        "issuer_organization_id": str(test_organization.id),
        "subject_agent_id": str(test_agent.id),
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "test"}
    }
    res = client.post("/credentials", json=cred_data, headers={"X-Mock-Principal-Org-Id": str(test_organization.id)})
    assert res.status_code == 201, res.text
    cred_id = res.json()["id"]
    
    # Revoke it
    revoke_res = client.post(f"/credentials/{cred_id}/revoke", headers={"X-Mock-Principal-Org-Id": str(test_organization.id)}, json={"reason": "test"})
    assert revoke_res.status_code == 200
    
    # Verify via API (will cache)
    vc_jwt = res.json()["vc_jwt"]
    verify_res = client.post("/credentials/verify", json={"vc_jwt": vc_jwt})
    assert verify_res.status_code == 200, verify_res.text
    assert not verify_res.json()["valid"]
    assert verify_res.json()["reason_code"] == "CREDENTIAL_REVOKED"
    
    # Find cache key
    import app.services.status_list_service as sl_service
    cache_keys = list(sl_service._STATUS_LIST_CACHE.keys())
    assert len(cache_keys) > 0
    key = cache_keys[-1] # the latest one
    
    # Tamper cache: modify the JWT payload but keep same signature (makes it invalid!)
    original_jwt = sl_service._STATUS_LIST_CACHE[key]
    parts = original_jwt.split(".")
    # Tamper payload
    tampered_payload = base64.urlsafe_b64encode(b'{"iss": "tampered"}').decode('ascii').rstrip("=")
    tampered_jwt = f"{parts[0]}.{tampered_payload}.{parts[2]}"
    sl_service._STATUS_LIST_CACHE[key] = tampered_jwt
    
    # Verify again - must fail cryptographic verification
    verify_res2 = client.post("/credentials/verify", json={"vc_jwt": vc_jwt})
    assert verify_res2.status_code == 200
    assert not verify_res2.json()["valid"]
    assert verify_res2.json()["reason_code"] == "STATUS_VERIFICATION_FAILED"

def test_db_independence(setup_app_overrides, setup_db, test_organization, test_agent, clear_cache, monkeypatch):
    # Mock HTTP fetch to use TestClient
    def mock_fetch(url):
        list_id = url.split("/")[-1]
        res = client.get(f"/.well-known/status-lists/{list_id}")
        if res.status_code == 200:
            return res.content
        raise Exception("Not found")
    import app.services.status_list_service as sl_service
    monkeypatch.setattr(sl_service, "fetch_status_list_artifact", mock_fetch)
    
    # Issue credential
    cred_data = {
        "issuer_organization_id": str(test_organization.id),
        "subject_agent_id": str(test_agent.id),
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "test"}
    }
    res = client.post("/credentials", json=cred_data, headers={"X-Mock-Principal-Org-Id": str(test_organization.id)})
    assert res.status_code == 201, res.text
    cred_id = res.json()["id"]
    vc_jwt = res.json()["vc_jwt"]
    
    from uuid import UUID
    # DELETE from Postgres
    setup_db.query(VerifiableCredential).filter_by(id=UUID(cred_id)).delete()
    setup_db.commit()
    
    print(f"DEBUG_TEST: vc_jwt payload: {jwt.decode(vc_jwt, options={'verify_signature': False})}")
    
    # Verify purely via artifact endpoint
    verify_res = client.post("/credentials/verify", json={"vc_jwt": vc_jwt})
    print(f"DEBUG_TEST: verify_res={verify_res.json()}")
    assert verify_res.status_code == 200, verify_res.text
    assert verify_res.json()["valid"] is True
    assert verify_res.json()["local_credential_id"] is None

def test_ssrf_protection_rejects_localhost(monkeypatch):
    from app.utils.http_client import fetch_status_list_artifact, SSRFSecurityError
    # Patch socket to resolve to localhost
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))])
    
    with pytest.raises(SSRFSecurityError, match="unsafe or private IP"):
        fetch_status_list_artifact("https://example.com/status")

def test_ssrf_protection_rejects_metadata(monkeypatch):
    from app.utils.http_client import fetch_status_list_artifact, SSRFSecurityError
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('169.254.169.254', 443))])
    
    with pytest.raises(SSRFSecurityError, match="unsafe or private IP"):
        fetch_status_list_artifact("https://example.com/status")

def test_ssrf_protection_rejects_http():
    from app.utils.http_client import fetch_status_list_artifact, SSRFSecurityError
    with pytest.raises(SSRFSecurityError, match="Only HTTPS"):
        fetch_status_list_artifact("http://example.com/status")
        
def test_decompression_bomb():
    # Make a tiny gzip that decompresses to something huge
    import zlib
    compressor = zlib.compressobj(wbits=31)
    huge_data = b'0' * 50000
    compressed = compressor.compress(huge_data) + compressor.flush()
    b64 = base64.urlsafe_b64encode(compressed).decode('ascii').rstrip('=')
    encoded = f"u{b64}"
    
    with pytest.raises(ValueError, match="decodes to more than allowed length"):
        _decode_bitstring(encoded)
