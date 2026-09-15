import base64
import time
from datetime import datetime, timezone, timedelta
import jwt
from uuid import uuid4, UUID
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

from app.models.agent_identity import AgentIdentity
from app.models.agent_identity_key import AgentIdentityKey
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.verifiable_credential import VerifiableCredential
from app.models.challenge import Challenge
from app.services.vp_auth_service import verify_vp_and_consume_challenge, VPAuthError, create_challenge
import pytest
from app.main import app
from app.database.connection import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import Base

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def override_get_db():
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _override
    yield _override
    app.dependency_overrides.pop(get_db, None)

def generate_ed25519_keypair():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return private_key, base64.b64encode(pub_bytes).decode('utf-8')

@pytest.fixture
def test_setup(override_get_db):
    db = next(override_get_db())
    org = Organization(name="Test Org", domain=f"test-{uuid4()}.org")
    db.add(org)
    db.commit()

    org_did = f"did:web:test.org:{org.id}"
    org_priv, org_pub = generate_ed25519_keypair()

    org_ident = OrganizationIdentity(organization_id=org.id, did=org_did, public_key=org_pub)
    db.add(org_ident)
    db.commit()

    org_key = OrganizationIdentityKey(
        organization_identity_id=org_ident.id,
        verification_method=f"{org_did}#key-1",
        public_key=org_pub,
        valid_from=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db.add(org_key)
    db.commit()

    agent = Agent(organization_id=org.id, name="Test Agent", agent_type="Service")
    db.add(agent)
    db.commit()

    agent_did = f"{org_did}:agents:{agent.id}"
    agent_priv, agent_pub = generate_ed25519_keypair()

    agent_ident = AgentIdentity(agent_id=agent.id, did=agent_did, public_key=agent_pub)
    db.add(agent_ident)
    db.commit()

    agent_key = AgentIdentityKey(
        agent_identity_id=agent_ident.id,
        verification_method=f"{agent_did}#key-1",
        public_key=agent_pub,
        valid_from=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db.add(agent_key)
    db.commit()

    # Create VC JWT
    now = int(time.time())
    vc_payload = {
        "iss": org_did,
        "sub": agent_did,
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
        "jti": str(uuid4()),
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential", "AgentCredential"],
            "credentialSubject": {
                "id": agent_did,
                "agent_name": "Test Agent"
            }
        }
    }
    vc_jwt = jwt.encode(vc_payload, org_priv, algorithm="EdDSA", headers={"kid": org_key.verification_method})

    # Save VC to DB (needed for verification)
    db.add(VerifiableCredential(
        id=UUID(vc_payload["jti"]),
        issuer_organization_id=org.id,
        subject_agent_id=agent.id,
        credential_type="AgentCredential",
        credential_data={},
        expires_at=datetime.fromtimestamp(vc_payload["exp"], tz=timezone.utc),
        status="active"
    ))
    db.commit()

    return {
        "db": db,
        "org_did": org_did,
        "agent_did": agent_did,
        "agent_priv": agent_priv,
        "agent_kid": agent_key.verification_method,
        "vc_jwt": vc_jwt,
        "org_priv": org_priv
    }

def test_vp_verification_success(test_setup):
    db = test_setup["db"]
    challenge = create_challenge(db)

    now = int(time.time())
    vp_payload = {
        "iss": test_setup["agent_did"],
        "aud": "did:web:trust.dpi.local",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": str(uuid4()),
        "nonce": challenge.nonce,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [test_setup["vc_jwt"]]
        }
    }

    vp_jwt = jwt.encode(vp_payload, test_setup["agent_priv"], algorithm="EdDSA", headers={"kid": test_setup["agent_kid"]})

    # Verify
    agent = verify_vp_and_consume_challenge(db, challenge.id, vp_jwt)
    assert agent.did == test_setup["agent_did"]

    # Challenge should be consumed
    db.refresh(challenge)
    assert challenge.consumed_at is not None

def test_vp_verification_consumed_challenge(test_setup):
    db = test_setup["db"]
    challenge = create_challenge(db)
    challenge.consumed_at = datetime.now(timezone.utc)
    db.commit()

    now = int(time.time())
    vp_payload = {
        "iss": test_setup["agent_did"],
        "aud": "did:web:trust.dpi.local",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "nonce": challenge.nonce,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [test_setup["vc_jwt"]]
        }
    }
    vp_jwt = jwt.encode(vp_payload, test_setup["agent_priv"], algorithm="EdDSA", headers={"kid": test_setup["agent_kid"]})

    with pytest.raises(VPAuthError, match="VP_CHALLENGE_INVALID"):
        verify_vp_and_consume_challenge(db, challenge.id, vp_jwt)

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)

def test_api_vp_login(test_setup, client, override_get_db):
    db = test_setup["db"]
    challenge = create_challenge(db)

    now = int(time.time())
    vp_payload = {
        "iss": test_setup["agent_did"],
        "aud": "did:web:trust.dpi.local",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "nonce": challenge.nonce,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [test_setup["vc_jwt"]]
        }
    }
    vp_jwt = jwt.encode(vp_payload, test_setup["agent_priv"], algorithm="EdDSA", headers={"kid": test_setup["agent_kid"]})

    response = client.post("/auth/login/vp", json={"challenge_id": str(challenge.id), "vp_jwt": vp_jwt})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_vp_verification_wrong_nonce(test_setup):
    db = test_setup["db"]
    challenge = create_challenge(db)

    now = int(time.time())
    vp_payload = {
        "iss": test_setup["agent_did"],
        "aud": "did:web:trust.dpi.local",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "nonce": "wrong-nonce",
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [test_setup["vc_jwt"]]
        }
    }
    vp_jwt = jwt.encode(vp_payload, test_setup["agent_priv"], algorithm="EdDSA", headers={"kid": test_setup["agent_kid"]})

    with pytest.raises(VPAuthError, match="VP_CHALLENGE_INVALID"):
        verify_vp_and_consume_challenge(db, challenge.id, vp_jwt)

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)

def test_api_vp_login(test_setup, client, override_get_db):
    from app.core.config import get_settings
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    settings = get_settings()
    
    # JWTIssuer requires an RSA private key because it uses RS256
    rsa_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings.auth_static_private_key = rsa_priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")
    db = test_setup["db"]
    challenge = create_challenge(db)

    now = int(time.time())
    vp_payload = {
        "iss": test_setup["agent_did"],
        "aud": "did:web:trust.dpi.local",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "nonce": challenge.nonce,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [test_setup["vc_jwt"]]
        }
    }
    vp_jwt = jwt.encode(vp_payload, test_setup["agent_priv"], algorithm="EdDSA", headers={"kid": test_setup["agent_kid"]})

    response = client.post("/auth/login/vp", json={"challenge_id": str(challenge.id), "vp_jwt": vp_jwt})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
