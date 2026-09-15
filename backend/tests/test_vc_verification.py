import base64
import pytest
import jwt
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.agent_identity import AgentIdentity
from app.models.verifiable_credential import VerifiableCredential
from app.services.organization_key_service import save_private_key
from app.services.vc_verification_service import (
    verify_vc_jwt,
    VALID,
    MALFORMED_VC,
    UNSUPPORTED_ALGORITHM,
    MISSING_KID,
    UNKNOWN_KID,
    ISSUER_NOT_FOUND,
    ISSUER_KEY_MISMATCH,
    SIGNATURE_INVALID,
    KEY_NOT_VALID_AT_ISSUANCE,
    CREDENTIAL_EXPIRED,
    CREDENTIAL_NOT_YET_VALID,
    SUBJECT_MISMATCH,
    JTI_MISMATCH,
    INVALID_VC_STRUCTURE,
    CREDENTIAL_REVOKED,
)


@compiles(JSONB, "sqlite")
def compile_jsonb(type_, compiler, **kw):
    return "JSON"


_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


from app.api.dependencies import get_current_principal, Principal
from fastapi import Request, HTTPException


def _mock_get_principal(request: Request):
    org_id = request.headers.get("X-Mock-Principal-Org-Id")
    if org_id:
        return Principal(organization_id=UUID(org_id), subject="mock|mock")
    raise HTTPException(status_code=401, detail="Unauthenticated")


@pytest.fixture(autouse=True)
def setup_app_overrides():
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_principal] = _mock_get_principal
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_principal, None)


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    yield


def _fresh_db():
    return _SessionLocal()


def _make_org_with_key(db, domain="issuer.example.com", key_offset_secs=-86400):
    org = Organization(id=uuid4(), name="Test Org", domain=domain, status="active")
    db.add(org)

    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_b64 = base64.b64encode(pub_bytes).decode("ascii")

    ident = OrganizationIdentity(
        id=uuid4(),
        organization_id=org.id,
        did=f"did:web:{domain}",
        public_key=pub_b64,
        key_algorithm="Ed25519",
        status="active",
    )
    db.add(ident)

    now = datetime.now(timezone.utc)
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=ident.id,
        verification_method=f"did:web:{domain}#key-1",
        public_key=pub_b64,
        key_algorithm="Ed25519",
        status="active",
        valid_from=now + timedelta(seconds=key_offset_secs),
    )
    db.add(key)
    db.commit()

    save_private_key(org.id, priv)
    return org, ident, key, priv


def _make_agent_identity(db, org, domain="issuer.example.com"):
    agent = Agent(id=uuid4(), organization_id=org.id, name="A", agent_type="bot", status="active")
    db.add(agent)
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")
    ident = AgentIdentity(
        id=uuid4(),
        agent_id=agent.id,
        did=f"did:web:{domain}:agents:{agent.id}",
        public_key=pub_b64,
        status="active",
    )
    db.add(ident)
    db.commit()
    db.refresh(agent)
    return agent, ident


def _build_vc_jwt(priv_key, kid, issuer_did, subject_did, jti=None,
                  iat_offset=0, exp_offset=None, nbf_offset=None):
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": issuer_did,
        "sub": subject_did,
        "jti": str(jti or uuid4()),
        "iat": now + iat_offset,
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential", "DPIAgentCredential"],
            "credentialSubject": {"id": subject_did},
        },
    }
    if exp_offset is not None:
        payload["exp"] = now + exp_offset
    if nbf_offset is not None:
        payload["nbf"] = now + nbf_offset

    return jwt.encode(payload, priv_key, algorithm="EdDSA", headers={"kid": kid})


# ── 1. Valid vc+jwt ───────────────────────────────────────────────────────────

def test_valid_vc_jwt():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did)
    result = verify_vc_jwt(token, db)

    assert result.valid is True, result.message
    assert result.reason_code == VALID
    assert result.issuer_did == ident.did
    assert result.subject_did == agent_ident.did
    assert result.signature_status == "valid"
    assert result.credential_type == "DPIAgentCredential"
    db.close()


def test_valid_vc_jwt_via_api():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)
    key_ver_method = key.verification_method
    ident_did = ident.did
    agent_ident_did = agent_ident.did
    db.close()

    token = _build_vc_jwt(priv, key_ver_method, ident_did, agent_ident_did)
    response = client.post("/credentials/verify", json={"vc_jwt": token})

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["valid"] is True
    assert data["reason_code"] == VALID


# ── 2. Tampered payload ───────────────────────────────────────────────────────

def test_tampered_payload():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did)
    header, payload, sig = token.split(".")
    
    import json
    decoded_payload = jwt.decode(token, options={"verify_signature": False})
    decoded_payload["sub"] = "did:web:evil-subject"
    bad = base64.urlsafe_b64encode(json.dumps(decoded_payload).encode()).rstrip(b"=").decode()
    tampered = f"{header}.{bad}.{sig}"

    result = verify_vc_jwt(tampered, db)
    assert result.valid is False
    assert result.reason_code == SIGNATURE_INVALID
    db.close()


# ── 3. Tampered signature ─────────────────────────────────────────────────────

def test_tampered_signature():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did)
    header, payload, _ = token.split(".")
    bad_sig = base64.urlsafe_b64encode(b"x" * 64).rstrip(b"=").decode()
    tampered = f"{header}.{payload}.{bad_sig}"

    result = verify_vc_jwt(tampered, db)
    assert result.valid is False
    assert result.reason_code == SIGNATURE_INVALID
    db.close()


# ── 4. Wrong public key (signed by different key than registered) ─────────────

def test_wrong_public_key():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    different_priv = Ed25519PrivateKey.generate()
    token = _build_vc_jwt(different_priv, key.verification_method, ident.did, agent_ident.did)

    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == SIGNATURE_INVALID
    db.close()


# ── 5. Unknown issuer ─────────────────────────────────────────────────────────

def test_unknown_issuer():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, "did:web:unknown.org", agent_ident.did)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == ISSUER_NOT_FOUND
    db.close()


# ── 6. Unknown kid ────────────────────────────────────────────────────────────

def test_unknown_kid():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, f"{ident.did}#key-99", ident.did, agent_ident.did)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == UNKNOWN_KID
    db.close()


# ── 7. kid from another organization ─────────────────────────────────────────

def test_kid_from_another_org():
    db = _fresh_db()
    org1, ident1, key1, priv1 = _make_org_with_key(db, domain="org1.example.com")
    org2, ident2, key2, priv2 = _make_org_with_key(db, domain="org2.example.com")
    _, agent_ident = _make_agent_identity(db, org1, org1.domain)

    token = _build_vc_jwt(priv1, key2.verification_method, ident1.did, agent_ident.did)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == ISSUER_KEY_MISMATCH
    db.close()


# ── 8. Missing kid ────────────────────────────────────────────────────────────

def test_missing_kid():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": ident.did, "sub": agent_ident.did,
        "jti": str(uuid4()), "iat": now,
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential"],
            "credentialSubject": {"id": agent_ident.did},
        },
    }
    token = jwt.encode(payload, priv, algorithm="EdDSA")

    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == MISSING_KID
    db.close()


# ── 9. alg=none ───────────────────────────────────────────────────────────────

def test_alg_none():
    db = _fresh_db()
    result = verify_vc_jwt(
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJpc3MiOiJkaWQ6d2ViOmV2aWwifQ.",
        db,
    )
    assert result.valid is False
    assert result.reason_code == UNSUPPORTED_ALGORITHM
    db.close()


# ── 10. Unsupported algorithm (HS256) ─────────────────────────────────────────

def test_unsupported_algorithm_hs256():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {"iss": ident.did, "sub": "did:web:x", "jti": str(uuid4()), "iat": now}
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        token = jwt.encode(payload, "secret", algorithm="HS256",
                           headers={"kid": key.verification_method})

    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == UNSUPPORTED_ALGORITHM
    db.close()


# ── 11. Expired VC ────────────────────────────────────────────────────────────

def test_expired_vc():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, exp_offset=-60)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == CREDENTIAL_EXPIRED
    assert result.signature_status == "expired"
    db.close()


# ── 12. Not-yet-valid VC (nbf in future) ─────────────────────────────────────

def test_not_yet_valid_vc():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, nbf_offset=3600)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == CREDENTIAL_NOT_YET_VALID
    db.close()


# ── 13. Wrong iss ─────────────────────────────────────────────────────────────

def test_wrong_iss():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    token = _build_vc_jwt(priv, key.verification_method, "did:web:wrong.example", agent_ident.did)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == ISSUER_NOT_FOUND
    db.close()


# ── 14. Subject mismatch (credentialSubject.id != sub) ───────────────────────

def test_subject_mismatch():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": ident.did,
        "sub": agent_ident.did,
        "jti": str(uuid4()), "iat": now,
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiableCredential", "DPIAgentCredential"],
            "credentialSubject": {"id": "did:web:someone-else.example"},
        },
    }
    token = jwt.encode(payload, priv, algorithm="EdDSA", headers={"kid": key.verification_method})
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == SUBJECT_MISMATCH
    db.close()


# ── 15. Invalid VC structure (missing vc claim) ───────────────────────────────

def test_invalid_vc_structure_missing_vc():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {"iss": ident.did, "sub": agent_ident.did, "jti": str(uuid4()), "iat": now}
    token = jwt.encode(payload, priv, algorithm="EdDSA", headers={"kid": key.verification_method})
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == INVALID_VC_STRUCTURE
    db.close()


def test_invalid_vc_structure_missing_context():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": ident.did, "sub": agent_ident.did, "jti": str(uuid4()), "iat": now,
        "vc": {"type": ["VerifiableCredential"], "credentialSubject": {"id": agent_ident.did}},
    }
    token = jwt.encode(payload, priv, algorithm="EdDSA", headers={"kid": key.verification_method})
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == INVALID_VC_STRUCTURE
    db.close()


def test_invalid_vc_structure_wrong_type():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": ident.did, "sub": agent_ident.did, "jti": str(uuid4()), "iat": now,
        "vc": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["SomeRandomType"],
            "credentialSubject": {"id": agent_ident.did},
        },
    }
    token = jwt.encode(payload, priv, algorithm="EdDSA", headers={"kid": key.verification_method})
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == INVALID_VC_STRUCTURE
    db.close()


# ── 16. Retired key — iat within validity interval (VALID) ───────────────────

def test_retired_key_historically_valid():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db, key_offset_secs=-3600)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    retire_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    key.status = "retired"
    key.valid_until = retire_time
    db.commit()

    # iat = 45 minutes ago - inside [valid_from, valid_until]
    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, iat_offset=-45 * 60)
    result = verify_vc_jwt(token, db)
    assert result.valid is True, result.message
    assert result.reason_code == VALID
    db.close()


# ── 17. Retired key — iat outside validity interval ───────────────────────────

def test_retired_key_outside_validity_interval():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db, key_offset_secs=-120)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    retire_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    key.status = "retired"
    key.valid_until = retire_time
    db.commit()

    # iat = now, after valid_until
    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, iat_offset=0)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == KEY_NOT_VALID_AT_ISSUANCE
    assert result.signature_status == "key_lifecycle"
    db.close()


# ── 18. Private key not in response ───────────────────────────────────────────

def test_private_key_not_in_response():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)
    key_ver_method = key.verification_method
    ident_did = ident.did
    agent_ident_did = agent_ident.did
    db.close()

    token = _build_vc_jwt(priv, key_ver_method, ident_did, agent_ident_did)
    response = client.post("/credentials/verify", json={"vc_jwt": token})
    response_str = str(response.json())
    assert "PRIVATE" not in response_str
    assert "-----BEGIN" not in response_str


# ── 19. Fabric status does not override cryptographic failure ─────────────────

def test_fabric_does_not_override_crypto_failure():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    cred_id = uuid4()
    now = datetime.now(timezone.utc)
    cred = VerifiableCredential(
        id=cred_id,
        issuer_organization_id=org.id,
        subject_agent_id=agent_ident.agent_id,
        credential_type="DPIAgentCredential",
        credential_data={},
        status="active",
        issued_at=now,
    )
    db.add(cred)
    db.commit()

    good_token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, jti=cred_id)
    header, payload, _ = good_token.split(".")
    bad_sig = base64.urlsafe_b64encode(b"y" * 64).rstrip(b"=").decode()
    tampered = f"{header}.{payload}.{bad_sig}"

    result = verify_vc_jwt(tampered, db)
    assert result.valid is False
    assert result.reason_code == SIGNATURE_INVALID
    db.close()


# ── 20. Revocation is surfaced ────────────────────────────────────────────────

def test_revoked_credential_surfaced():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    cred_id = uuid4()
    now = datetime.now(timezone.utc)
    cred = VerifiableCredential(
        id=cred_id,
        issuer_organization_id=org.id,
        subject_agent_id=agent_ident.agent_id,
        credential_type="DPIAgentCredential",
        credential_data={},
        status="revoked",
        issued_at=now,
        revoked_at=now,
        revocation_reason="test",
    )
    db.add(cred)
    db.commit()

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, jti=cred_id)
    result = verify_vc_jwt(token, db)
    assert result.valid is False
    assert result.reason_code == CREDENTIAL_REVOKED
    assert result.local_status == "revoked"
    assert result.signature_status == "valid"
    db.close()


# ── 21. DB record not required for cryptographic validity ─────────────────────

def test_verification_does_not_require_db_record():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    external_jti = uuid4()
    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, jti=external_jti)
    result = verify_vc_jwt(token, db)
    assert result.valid is True, result.message
    assert result.local_credential_id is None
    assert result.local_status is None
    db.close()


# ── 22. Malformed JWT ─────────────────────────────────────────────────────────

def test_malformed_jwt():
    db = _fresh_db()
    assert verify_vc_jwt("not-a-jwt", db).reason_code == MALFORMED_VC
    assert verify_vc_jwt("aGVhZGVy.cGF5bG9hZA", db).reason_code == MALFORMED_VC
    db.close()


# ── 23. Fabric transaction_id surfaced ────────────────────────────────────────

def test_fabric_transaction_id_not_on_credential():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)

    cred_id = uuid4()
    now = datetime.now(timezone.utc)
    cred = VerifiableCredential(
        id=cred_id,
        issuer_organization_id=org.id,
        subject_agent_id=agent_ident.agent_id,
        credential_type="DPIAgentCredential",
        credential_data={},
        status="active",
        issued_at=now,
    )
    db.add(cred)
    db.commit()

    token = _build_vc_jwt(priv, key.verification_method, ident.did, agent_ident.did, jti=cred_id)
    result = verify_vc_jwt(token, db)
    assert result.valid is True, result.message
    assert result.fabric_transaction_id is None
    db.close()


# ── 24. API returns 200 even for invalid (signal via valid field) ─────────────

def test_api_200_for_invalid_vc():
    response = client.post("/credentials/verify", json={"vc_jwt": "not-a-jwt"})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["reason_code"] == MALFORMED_VC


# ── 25. Legacy GET verify endpoint still works ────────────────────────────────

def test_legacy_get_verify_still_works():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)
    org_id = str(org.id)
    agent_id = str(agent_ident.agent_id)
    db.close()

    cred_data = {
        "issuer_organization_id": org_id,
        "subject_agent_id": agent_id,
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "legacy"},
    }
    issue_resp = client.post(
        "/credentials", json=cred_data,
        headers={"X-Mock-Principal-Org-Id": org_id},
    )
    assert issue_resp.status_code == 201, issue_resp.json()
    cred_id = issue_resp.json()["id"]

    verify_resp = client.get(
        f"/credentials/{cred_id}/verify",
        headers={"X-Mock-Principal-Org-Id": org_id},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["valid"] is True



def test_issue_then_verify_via_artifact_endpoint():
    db = _fresh_db()
    org, ident, key, priv = _make_org_with_key(db)
    _, agent_ident = _make_agent_identity(db, org, org.domain)
    org_id = str(org.id)
    agent_id = str(agent_ident.agent_id)
    ident_did = ident.did
    agent_ident_did = agent_ident.did
    db.close()

    cred_data = {
        "issuer_organization_id": org_id,
        "subject_agent_id": agent_id,
        "credential_type": "DPIAgentCredential",
        "credential_data": {"role": "pipeline_test"},
    }
    issue_resp = client.post(
        "/credentials", json=cred_data,
        headers={"X-Mock-Principal-Org-Id": org_id},
    )
    assert issue_resp.status_code == 201, issue_resp.json()
    vc_jwt = issue_resp.json()["vc_jwt"]
    assert vc_jwt is not None

    verify_resp = client.post("/credentials/verify", json={"vc_jwt": vc_jwt})
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    print("DEBUG:", data)
    assert data["valid"] is True
    assert data["reason_code"] == VALID
    assert data["issuer_did"] == ident_did
    assert data["subject_did"] == agent_ident_did
    assert data["local_credential_id"] == issue_resp.json()["id"]
    assert data["local_status"] == "active"
