import pytest
import responses
from unittest.mock import patch
from app.services.did_web_resolution_service import (
    resolve_did_web,
    _build_did_web_url,
    DIDResolutionError,
    _DID_DOCUMENT_CACHE
)
from app.utils.http_client import HTTPClientError

@pytest.fixture(autouse=True)
def clear_cache():
    _DID_DOCUMENT_CACHE.clear()

@pytest.fixture(autouse=True)
def mock_dns(monkeypatch):
    import socket
    original_getaddrinfo = socket.getaddrinfo
    def mock_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if host.endswith(".example.com") or host.endswith(".org") or host == "foreign.org":
            # Return public IP to pass the SSRF check
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', port))]
        return original_getaddrinfo(host, port, family, type, proto, flags)
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

@pytest.fixture
def mock_fetch_json(monkeypatch):
    from app.utils.http_client import HTTPClientError
    responses_map = {}
    def _mock_fetch(url, **kwargs):
        if url in responses_map:
            res = responses_map[url]
            if isinstance(res, Exception):
                raise res
            return res
        raise HTTPClientError(f"Mock not found for {url}")
    monkeypatch.setattr("app.services.did_web_resolution_service.fetch_json_artifact", _mock_fetch)
    return responses_map

def test_build_did_web_url():
    assert _build_did_web_url("did:web:example.com") == "https://example.com/.well-known/did.json"
    assert _build_did_web_url("did:web:example.com:agents:123") == "https://example.com/agents/123/did.json"
    
    with pytest.raises(DIDResolutionError):
        _build_did_web_url("did:key:z6MkhaXgBZDvotDkL5257faiztiCEsJUTCwkU")

def test_resolve_did_web_success(mock_fetch_json):
    did = "did:web:test.example.com"
    url = "https://test.example.com/.well-known/did.json"

    did_doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did,
        "verificationMethod": [{
            "id": f"{did}#key-1",
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyBase64": "testBase64Key=="
        }]
    }

    import json
    mock_fetch_json[url] = json.dumps(did_doc).encode("utf-8")

    resolved = resolve_did_web(did)
    assert resolved == did_doc
    assert _DID_DOCUMENT_CACHE.get(did) == did_doc

def test_resolve_did_web_invalid_json(mock_fetch_json):
    did = "did:web:test.example.com"
    url = "https://test.example.com/.well-known/did.json"

    mock_fetch_json[url] = b"not json"

    with pytest.raises(DIDResolutionError, match="Invalid JSON"):
        resolve_did_web(did)

def test_resolve_did_web_missing_id(mock_fetch_json):
    did = "did:web:test.example.com"
    url = "https://test.example.com/.well-known/did.json"

    did_doc = {
        "verificationMethod": [{
            "id": f"{did}#key-1",
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyBase64": "testBase64Key=="
        }]
    }

    import json
    mock_fetch_json[url] = json.dumps(did_doc).encode("utf-8")

    with pytest.raises(DIDResolutionError, match="DID Document ID mismatch"):
        resolve_did_web(did)

def test_resolve_did_web_unsupported_key_type(mock_fetch_json):
    did = "did:web:test.example.com"
    url = "https://test.example.com/.well-known/did.json"

    did_doc = {
        "id": did,
        "verificationMethod": [{
            "id": f"{did}#key-1",
            "type": "RsaVerificationKey2018",
            "controller": did,
            "publicKeyBase64": "testBase64Key=="
        }]
    }

    import json
    mock_fetch_json[url] = json.dumps(did_doc).encode("utf-8")

    with pytest.raises(DIDResolutionError, match="Unsupported verification method type"):
        resolve_did_web(did)
