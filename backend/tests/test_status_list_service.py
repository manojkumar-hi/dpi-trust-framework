import pytest
import jwt
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import base64

from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from app.services.status_list_service import (
    _set_bit, _get_bit, _encode_bitstring, _decode_bitstring,
    allocate_index, set_status, build_and_sign_status_list_vc, verify_and_check_status,
    StatusListError, MAX_INDEX, BITSTRING_LENGTH
)
from app.models.bitstring_status_list import BitstringStatusList
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_keys(monkeypatch):
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    b64_pub = base64.b64encode(pub_bytes).decode('ascii')
    
    def mock_load_private_key(org_id):
        return private_key

    monkeypatch.setattr("app.services.status_list_service.load_private_key", mock_load_private_key)
    return b64_pub, private_key

def setup_issuer(db: Session, b64_pub: str):
    org = Organization(id=uuid4(), name="Test Org", domain="test.org")
    db.add(org)
    
    did = f"did:web:test.org"
    identity = OrganizationIdentity(
        id=uuid4(),
        organization_id=org.id,
        did=did,
        public_key=b64_pub
    )
    db.add(identity)
    
    kid = f"{did}#key-1"
    now = datetime.now(timezone.utc)
    key = OrganizationIdentityKey(
        id=uuid4(),
        organization_identity_id=identity.id,
        verification_method=kid,
        public_key=b64_pub,
        valid_from=now - timedelta(days=1)
    )
    db.add(key)
    db.commit()
    return did, kid

def test_bitstring_encode_decode():
    bitstring = bytearray(BITSTRING_LENGTH)
    # Test setting a few bits
    _set_bit(bitstring, 0, True)
    _set_bit(bitstring, MAX_INDEX - 1, True)
    _set_bit(bitstring, 50, True)
    
    encoded = _encode_bitstring(bytes(bitstring))
    assert encoded.startswith("u")
    
    decoded = _decode_bitstring(encoded)
    assert len(decoded) == BITSTRING_LENGTH
    
    assert _get_bit(decoded, 0) is True
    assert _get_bit(decoded, MAX_INDEX - 1) is True
    assert _get_bit(decoded, 50) is True
    assert _get_bit(decoded, 1) is False

def test_bitstring_out_of_bounds():
    bitstring = bytearray(BITSTRING_LENGTH)
    with pytest.raises(ValueError):
        _set_bit(bitstring, MAX_INDEX, True)
    with pytest.raises(ValueError):
        _get_bit(bitstring, -1)

def test_index_allocation_and_rollover(db: Session):
    did = "did:web:alloc.test"
    list_id_1, idx_1 = allocate_index(db, did)
    assert idx_1 == 0
    
    list_id_2, idx_2 = allocate_index(db, did)
    assert idx_2 == 1
    assert list_id_1 == list_id_2
    
    # Simulate list filling up
    status_list = db.get(BitstringStatusList, list_id_1)
    status_list.current_index = MAX_INDEX
    db.commit()
    
    list_id_3, idx_3 = allocate_index(db, did)
    assert idx_3 == 0
    assert list_id_3 != list_id_1

def test_set_status(db: Session):
    did = "did:web:status.test"
    list_id, idx = allocate_index(db, did)
    db.commit()
    
    set_status(db, list_id, idx, revoked=True)
    
    status_list = db.get(BitstringStatusList, list_id)
    assert _get_bit(status_list.bitstring, idx) is True
    
    set_status(db, list_id, idx, revoked=False)
    status_list = db.get(BitstringStatusList, list_id)
    assert _get_bit(status_list.bitstring, idx) is False

def test_build_and_verify_vc(db: Session, mock_keys):
    b64_pub, _ = mock_keys
    did, kid = setup_issuer(db, b64_pub)
    
    list_id, idx = allocate_index(db, did)
    db.commit()
    
    # Initially 0
    vc_jwt = build_and_sign_status_list_vc(db, list_id, "https://test.org")
    
    # Verify bit 0 is false
    is_revoked = verify_and_check_status(db, vc_jwt, idx)
    assert is_revoked is False
    
    # Revoke
    set_status(db, list_id, idx, revoked=True)
    vc_jwt_revoked = build_and_sign_status_list_vc(db, list_id, "https://test.org")
    
    # Verify bit 0 is true
    is_revoked = verify_and_check_status(db, vc_jwt_revoked, idx)
    assert is_revoked is True
    
    # Other bit is false
    assert verify_and_check_status(db, vc_jwt_revoked, idx + 1) is False

def test_verify_tampered_vc(db: Session, mock_keys):
    b64_pub, _ = mock_keys
    did, _ = setup_issuer(db, b64_pub)
    list_id, idx = allocate_index(db, did)
    db.commit()
    
    vc_jwt = build_and_sign_status_list_vc(db, list_id, "https://test.org")
    
    # Tamper with the JWT by modifying the payload
    parts = vc_jwt.split('.')
    tampered_jwt = f"{parts[0]}.eyJ0YW1wZXJlZCI6dHJ1ZX0.{parts[2]}"
    
    with pytest.raises(StatusListError):
        verify_and_check_status(db, tampered_jwt, idx)

def test_verify_key_lifecycle(db: Session, mock_keys):
    b64_pub, _ = mock_keys
    did, kid = setup_issuer(db, b64_pub)
    list_id, idx = allocate_index(db, did)
    db.commit()
    
    vc_jwt = build_and_sign_status_list_vc(db, list_id, "https://test.org")
    
    # Simulate key expiry before the token was issued (in the DB)
    # The VC is already signed, but the DB says the key expired yesterday
    key = db.query(OrganizationIdentityKey).filter_by(verification_method=kid).first()
    key.valid_until = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    
    with pytest.raises(StatusListError, match="expired at issuance time"):
        verify_and_check_status(db, vc_jwt, idx)

