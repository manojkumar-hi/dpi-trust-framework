import pytest
import math
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy import create_engine, StaticPool, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, 'sqlite')
def compile_jsonb(type_, compiler, **kw):
    return "JSON"

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.audit_record import AuditRecord
from app.models.delegation_event import DelegationEvent
from app.schemas.audit import AuditRecordCreate
from app.schemas.agent import AgentCreate

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_app_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

from app.api.dependencies import get_current_principal, Principal
from fastapi import Request
from uuid import UUID

def mock_get_principal(request: Request):
    org_id = request.headers.get("x-mock-principal-org-id")
    if org_id:
        return Principal(organization_id=UUID(org_id), subject="mock|mock")
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Unauthenticated: Principal required")

app.dependency_overrides[get_current_principal] = mock_get_principal
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def test_org(setup_db):
    org = Organization(id=uuid4(), name="Test Org", domain="test.org", status="active")
    setup_db.add(org)
    setup_db.commit()
    setup_db.refresh(org)
    return org

@pytest.fixture
def test_agent(setup_db, test_org):
    agent = Agent(
        id=uuid4(),
        organization_id=test_org.id,
        name="Test Agent",
        agent_type="bot",
        status="active"
    )
    setup_db.add(agent)
    setup_db.commit()
    setup_db.refresh(agent)
    return agent


def test_sensitive_data_exclusion():
    from app.services.audit_service import _strip_sensitive_data
    
    dirty_data = {
        "public_info": "safe",
        "private_key": "supersecret",
        "nested": {
            "token": "bearer123",
            "other": "ok"
        }
    }
    
    clean_data = _strip_sensitive_data(dirty_data)
    assert clean_data["public_info"] == "safe"
    assert clean_data["private_key"] == "[REDACTED]"
    assert clean_data["nested"]["token"] == "[REDACTED]"
    assert clean_data["nested"]["other"] == "ok"


@patch("app.api.authorization_dependency.SessionLocal")
def test_authorization_allow_audit_persists(mock_session_local, setup_db, test_org, test_agent):
    mock_session_local.return_value = setup_db
    response = client.post(
        f"/agents/{test_agent.id}/simulated-sensitive-op",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id), "X-Correlation-ID": "test-corr-1"}
    )
    # The current policy evaluates to DENY
    assert response.status_code == 403
    
    records = setup_db.scalars(select(AuditRecord).where(AuditRecord.correlation_id == "test-corr-1")).all()
    assert len(records) == 1
    assert records[0].event_category == "AUTHORIZATION"
    assert records[0].authorization_decision == "DENY"


@patch("app.api.authorization_dependency.SessionLocal")
@patch("app.api.authorization_dependency.AuditService.create_audit_record")
def test_authorization_audit_failure_fails_closed(mock_audit, mock_session_local, test_org, test_agent, setup_db):
    mock_session_local.return_value = setup_db
    mock_audit.side_effect = Exception("DB failure")
    
    response = client.post(
        f"/agents/{test_agent.id}/simulated-sensitive-op",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    # Fail closed
    assert response.status_code == 500


@patch("app.services.agent_service.AuditService.create_audit_record")
def test_mutation_rollback_on_audit_failure(mock_audit, setup_db, test_org):
    from app.services.agent_service import create_agent
    
    mock_audit.side_effect = Exception("Audit DB fail")
    
    agent_data = AgentCreate(
        organization_id=test_org.id,
        name="Test Rollback Agent",
        agent_type="bot",
        agent_version="1.0"
    )
    
    try:
        create_agent(setup_db, agent_data)
        pytest.fail("Should have raised exception")
    except Exception:
        pass
        
    agent_in_db = setup_db.scalars(select(Agent).where(Agent.name == "Test Rollback Agent")).first()
    assert agent_in_db is None


def test_trust_ingestion_audit(setup_db, test_org, test_agent):
    corr_id = "trust-corr-id"
    payload = {
        "outcome": "success",
        "evidence_quality": 1.0,
        "informative_value": 0.5,
        "action_metadata": {}
    }
    
    response = client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json=payload,
        headers={"X-Mock-Principal-Org-Id": str(test_org.id), "X-Correlation-ID": corr_id}
    )
    assert response.status_code == 201
    
    records = setup_db.scalars(select(AuditRecord).where(AuditRecord.correlation_id == corr_id)).all()
    assert len(records) == 1
    assert records[0].event_category == "TRUST"
    assert records[0].event_type == "evidence_ingested"
    assert records[0].trust_snapshot is not None
    assert "t" in records[0].trust_snapshot


def test_audit_query_api(setup_db, test_org, test_agent):
    from app.services.audit_service import AuditService
    AuditService.create_audit_record(setup_db, AuditRecordCreate(
        correlation_id="q-corr-1",
        event_category="TEST",
        event_type="test",
        subject_agent_id=test_agent.id,
        actor_organization_id=test_org.id
    ))
    setup_db.commit()
    
    resp = client.get("/audit?correlation_id=q-corr-1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["correlation_id"] == "q-corr-1"
