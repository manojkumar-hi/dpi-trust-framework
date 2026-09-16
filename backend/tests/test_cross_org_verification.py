import pytest
import responses
import jwt
import base64
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from uuid import uuid4
from app.utils.http_client import HTTPClientError

from sqlalchemy.orm import Session
from app.services.vc_verification_service import verify_vc_jwt
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.services.did_web_resolution_service import _DID_DOCUMENT_CACHE

from app.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def clear_cache():
    _DID_DOCUMENT_CACHE.clear()

@pytest.fixture(autouse=True)
def mock_dns(monkeypatch):
    import socket
    original_getaddrinfo = socket.getaddrinfo
    def mock_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if host.endswith(".org"):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', port))]
        return original_getaddrinfo(host, port, family, type, proto, flags)
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

def _generate_ed25519_keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    pub_key_b64 = base64.b64encode(pub_bytes).decode('ascii')
    
    return private_key, pub_key_b64

@pytest.fixture
def mock_fetch_json(monkeypatch):
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

@pytest.fixture
def mock_settings(monkeypatch):
    class MockSettings:
        did_web_domain = "local.dpi.trust"
    monkeypatch.setattr("app.core.config.get_settings", MockSettings)

def test_cross_org_verification_success(db_session: Session, mock_settings, mock_fetch_json):
    # We are simulating Verifier at "local.dpi.trust" verifying a VC from "foreign.org"
    foreign_did = "did:web:foreign.org"
    foreign_kid = f"{foreign_did}#key-1"
    
    private_key, pub_key_b64 = _generate_ed25519_keypair()
    
    # Setup HTTP mock for foreign DID Document
    did_doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": foreign_did,
        "verificationMethod": [{
            "id": foreign_kid,
            "type": "Ed25519VerificationKey2020",
            "controller": foreign_did,
            "publicKeyBase64": pub_key_b64
        }]
    }
    import json
    mock_fetch_json["https://foreign.org/.well-known/did.json"] = json.dumps(did_doc).encode("utf-8")
    
    # Generate VC
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    
    vc_payload = {
        "iss": foreign_did,
        "sub": "did:web:subject.org",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(days=1)).timestamp()),
        "jti": jti,
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential"],
            "credentialSubject": {
                "id": "did:web:subject.org"
            }
        }
    }
    
    vc_jwt = jwt.encode(
        vc_payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": foreign_kid}
    )
    
    result = verify_vc_jwt(vc_jwt, db_session)
    assert result.valid is True
    assert result.issuer_did == foreign_did
    assert result.reason_code == "VALID"

def test_cross_org_verification_database_poisoning(db_session: Session, mock_settings, mock_fetch_json):
    """
    Test: foreign DID exists as a malicious/stale local DB row with a DIFFERENT public key.
    Verification MUST use the authoritative foreign DID resolution path, NOT the poisoned local key.
    """
    foreign_did = "did:web:foreign.org"
    foreign_kid = f"{foreign_did}#key-1"
    
    # Malicious key in DB
    malicious_private, malicious_pub = _generate_ed25519_keypair()
    
    org_identity = OrganizationIdentity(
        organization_id=uuid4(),
        did=foreign_did,
        public_key=malicious_pub,
        status="active"
    )
    db_session.add(org_identity)
    db_session.flush()
    
    org_key = OrganizationIdentityKey(
        organization_identity_id=org_identity.id,
        verification_method=foreign_kid,
        public_key=malicious_pub,
        status="active",
        valid_from=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(org_key)
    db_session.commit()
    
    # Authoritative key on HTTPS
    authoritative_private, authoritative_pub = _generate_ed25519_keypair()
    
    did_doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": foreign_did,
        "verificationMethod": [{
            "id": foreign_kid,
            "type": "Ed25519VerificationKey2020",
            "controller": foreign_did,
            "publicKeyBase64": authoritative_pub
        }]
    }
    import json
    mock_fetch_json["https://foreign.org/.well-known/did.json"] = json.dumps(did_doc).encode("utf-8")
    
    now = datetime.now(timezone.utc)
    vc_payload = {
        "iss": foreign_did,
        "sub": "did:web:subject.org",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "jti": str(uuid4()),
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential"],
            "credentialSubject": {"id": "did:web:subject.org"}
        }
    }
    
    # Case 1: Sign with Authoritative key -> should succeed
    vc_jwt_auth = jwt.encode(vc_payload, authoritative_private, algorithm="EdDSA", headers={"kid": foreign_kid})
    result_auth = verify_vc_jwt(vc_jwt_auth, db_session)
    assert result_auth.valid is True
    
    # Case 2: Sign with Malicious local key -> should fail because HTTP fetched key is authoritative
    vc_jwt_mal = jwt.encode(vc_payload, malicious_private, algorithm="EdDSA", headers={"kid": foreign_kid})
    result_mal = verify_vc_jwt(vc_jwt_mal, db_session)
    assert result_mal.valid is False
    assert result_mal.reason_code == "SIGNATURE_INVALID"

def test_cross_org_verification_key_mismatch(db_session: Session, mock_settings, mock_fetch_json):
    """
    Test: DID Document key A + VC signed with key B -> FAIL
    """
    foreign_did = "did:web:foreign.org"
    foreign_kid = f"{foreign_did}#key-1"
    
    # Key A (in DID Doc)
    _, pub_key_A = _generate_ed25519_keypair()
    
    # Key B (used to sign VC)
    priv_key_B, _ = _generate_ed25519_keypair()
    
    did_doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": foreign_did,
        "verificationMethod": [{
            "id": foreign_kid,
            "type": "Ed25519VerificationKey2020",
            "controller": foreign_did,
            "publicKeyBase64": pub_key_A
        }]
    }
    import json
    mock_fetch_json["https://foreign.org/.well-known/did.json"] = json.dumps(did_doc).encode("utf-8")
    
    now = datetime.now(timezone.utc)
    vc_payload = {
        "iss": foreign_did,
        "sub": "did:web:subject.org",
        "iat": int(now.timestamp()),
        "jti": str(uuid4()),
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential"],
            "credentialSubject": {"id": "did:web:subject.org"}
        }
    }
    
    # Sign with key B
    vc_jwt = jwt.encode(vc_payload, priv_key_B, algorithm="EdDSA", headers={"kid": foreign_kid})
    
    result = verify_vc_jwt(vc_jwt, db_session)
    assert result.valid is False
    assert result.reason_code == "SIGNATURE_INVALID"
