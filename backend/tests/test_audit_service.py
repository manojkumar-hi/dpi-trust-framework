import pytest
from uuid import uuid4
from sqlalchemy.orm import Session
from app.services.audit_service import AuditService, _strip_sensitive_data
from app.schemas.audit import AuditRecordCreate
from app.models.audit_record import AuditRecord
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

def test_strip_sensitive_data():
    raw_data = {
        "public_key": "some_pub",
        "private_key": "secret123",
        "nested": {
            "token": "tok_123",
            "safe_val": "abc"
        },
        "list_val": [
            {"password": "pass", "id": "1"}
        ]
    }
    cleaned = _strip_sensitive_data(raw_data)
    
    assert cleaned["public_key"] == "some_pub"
    assert cleaned["private_key"] == "[REDACTED]"
    assert cleaned["nested"]["token"] == "[REDACTED]"
    assert cleaned["nested"]["safe_val"] == "abc"
    assert cleaned["list_val"][0]["password"] == "[REDACTED]"
    assert cleaned["list_val"][0]["id"] == "1"

def test_create_audit_record(db: Session):
    correlation_id = uuid4().hex
    record_in = AuditRecordCreate(
        correlation_id=correlation_id,
        event_category="AUTHORIZATION",
        event_type="authorization_evaluated",
        actor_did="did:key:123",
        trust_snapshot={"t": 0.9, "u": 0.1, "rr": 0.05, "secret": "hide_me"},
        evidence_snapshot={"reason": "good"}
    )
    
    record = AuditService.create_audit_record(db, record_in)
    db.commit()
    
    # Assert
    saved_record = db.query(AuditRecord).filter_by(id=record.id).first()
    assert saved_record is not None
    assert saved_record.correlation_id == correlation_id
    assert saved_record.event_category == "AUTHORIZATION"
    assert saved_record.event_type == "authorization_evaluated"
    assert saved_record.trust_snapshot["t"] == 0.9
    assert saved_record.trust_snapshot["secret"] == "[REDACTED]"
    assert saved_record.event_version == 1

def test_get_audit_records(db: Session):
    correlation_id = uuid4().hex
    subject_agent_id = uuid4()
    record_in = AuditRecordCreate(
        correlation_id=correlation_id,
        event_category="TRUST",
        event_type="evidence_ingested",
        subject_agent_id=subject_agent_id
    )
    AuditService.create_audit_record(db, record_in)
    db.commit()
    
    records_by_corr = AuditService.get_audit_records(db, correlation_id=correlation_id)
    assert len(records_by_corr) == 1
    assert records_by_corr[0].correlation_id == correlation_id
    
    records_by_agent = AuditService.get_audit_records(db, subject_agent_id=subject_agent_id)
    assert len(records_by_agent) == 1
    assert records_by_agent[0].subject_agent_id == subject_agent_id
