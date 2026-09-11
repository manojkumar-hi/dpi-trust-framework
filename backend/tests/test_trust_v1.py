import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
import sqlalchemy.types as sqltypes

@compiles(JSONB, 'sqlite')
def compile_jsonb(type_, compiler, **kw):
    return "JSON"

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.agent_trust_state import AgentTrustState
from app.models.behavioral_evidence import BehavioralEvidence
from app.services.trust_service import TrustService

# Setup in-memory SQLite database for testing
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
    app.dependency_overrides.clear()

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

def test_01_new_agent(test_agent, test_org):
    response = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert math.isclose(data["trust"], 0.5, abs_tol=1e-5)
    assert math.isclose(data["uncertainty"], 1.0, abs_tol=1e-5)
    assert math.isclose(data["recent_risk"], 0.0, abs_tol=1e-5)

def test_02_one_successful_event(test_agent, test_org):
    response = client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={
            "outcome": "success",
            "evidence_quality": 1.0,
            "informative_value": 0.5,
            "action_metadata": {"action": "test"}
        },
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    assert response.status_code == 201

    trust_res = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = trust_res.json()
    assert data["trust"] > 0.5
    assert math.isclose(data["positive_evidence"], 0.5, abs_tol=1e-5)
    assert data["uncertainty"] < 1.0

def test_03_ten_successful_events(test_agent, test_org):
    for _ in range(10):
        client.post(
            f"/agents/{test_agent.id}/trust/evidence",
            json={
                "outcome": "success",
                "evidence_quality": 1.0,
                "informative_value": 0.5,
            },
            headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
        )

    trust_res = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = trust_res.json()
    assert data["trust"] > 0.5
    assert math.isclose(data["positive_evidence"], 5.0, abs_tol=1e-5)
    assert math.isclose(data["recent_risk"], 0.0, abs_tol=1e-5)

@pytest.mark.parametrize("severity", [1, 2, 4, 8, 16])
def test_04_to_08_violations(severity, test_agent, test_org):
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={
            "outcome": "failure",
            "evidence_quality": 1.0,
            "severity": severity
        },
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )

    trust_res = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = trust_res.json()
    assert data["trust"] < 0.5
    assert math.isclose(data["negative_evidence"], severity, abs_tol=1e-5)
    
    expected_rr = severity / 16.0
    assert math.isclose(data["recent_risk"], expected_rr, abs_tol=1e-5)

def test_09_critical_violation_after_strong_history(test_agent, test_org):
    # Strong history
    for _ in range(5):
        client.post(
            f"/agents/{test_agent.id}/trust/evidence",
            json={
                "outcome": "success",
                "evidence_quality": 1.0,
                "informative_value": 1.0,
            },
            headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
        )
    
    # Critical violation
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={
            "outcome": "failure",
            "evidence_quality": 1.0,
            "severity": 16
        },
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )

    trust_res = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = trust_res.json()
    assert math.isclose(data["recent_risk"], 1.0, abs_tol=1e-5)
    assert math.isclose(data["positive_evidence"], 5.0, abs_tol=1e-5)
    assert math.isclose(data["negative_evidence"], 16.0, abs_tol=1e-5)

def test_10_multiple_negative_events(test_agent, test_org):
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "failure", "evidence_quality": 1.0, "severity": 8},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "failure", "evidence_quality": 1.0, "severity": 8},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )

    trust_res = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = trust_res.json()
    # 1 - (1 - 0.5)*(1 - 0.5) = 1 - 0.25 = 0.75
    assert math.isclose(data["recent_risk"], 0.75, abs_tol=1e-5)
    assert data["recent_risk"] <= 1.0

def test_11_temporal_decay(test_agent, test_org, setup_db):
    past_time = datetime.now(timezone.utc) - timedelta(days=30)
    ev = BehavioralEvidence(
        agent_id=test_agent.id,
        timestamp=past_time,
        outcome="failure",
        severity=16,
        evidence_quality=1.0,
        created_at=past_time
    )
    setup_db.add(ev)
    setup_db.commit()

    trust_res = client.get(
        f"/agents/{test_agent.id}/trust",
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = trust_res.json()
    assert math.isclose(data["recent_risk"], 0.5, abs_tol=1e-5)

def test_12_evidence_quality(test_agent, test_org):
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "failure", "evidence_quality": 0.2, "severity": 16},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    trust_res = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)})
    assert math.isclose(trust_res.json()["recent_risk"], 0.2, abs_tol=1e-5)

def test_13_informative_value(test_agent, test_org):
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 0.01},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    res1 = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)}).json()
    assert math.isclose(res1["positive_evidence"], 0.01, abs_tol=1e-5)

def test_14_trust_farming(test_agent, test_org):
    for _ in range(20):
        client.post(
            f"/agents/{test_agent.id}/trust/evidence",
            json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0},
            headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
        )
    trust_res = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)})
    data = trust_res.json()
    assert math.isclose(data["positive_evidence"], TrustService.R_MAX_PER_WINDOW, abs_tol=1e-5)

def test_15_recovery(test_agent, test_org):
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "failure", "evidence_quality": 1.0, "severity": 4},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    res1 = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)}).json()
    
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    res2 = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)}).json()
    
    assert res2["trust"] > res1["trust"]
    assert math.isclose(res2["positive_evidence"], 1.0, abs_tol=1e-5)

def test_16_mathematical_invariants(test_agent, test_org):
    client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    data = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)}).json()
    b, d, u = data["belief"], data["disbelief"], data["uncertainty"]
    assert math.isclose(b + d + u, 1.0, abs_tol=1e-5)
    assert 0 <= b <= 1
    assert 0 <= d <= 1
    assert 0 <= u <= 1
    assert 0 <= data["trust"] <= 1
    assert 0 <= data["recent_risk"] <= 1

def test_17_out_of_order_timestamp(test_agent, test_org, setup_db):
    now = datetime.now(timezone.utc)
    state = AgentTrustState(
        id=uuid4(),
        agent_id=test_agent.id,
        positive_evidence_r=0, negative_evidence_s=0,
        current_window_start=now, current_window_r=0,
        last_updated_at=now
    )
    setup_db.add(state)
    setup_db.commit()

    future = now + timedelta(days=1)
    state.last_updated_at = future
    setup_db.commit()

    res = client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0},
        headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
    )
    assert res.status_code == 400
    assert "Out-of-order evidence" in res.json()["detail"]

def test_18_unauthorized_evidence_ingestion(test_agent):
    other_org_id = str(uuid4())
    res = client.post(
        f"/agents/{test_agent.id}/trust/evidence",
        json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0},
        headers={"X-Mock-Principal-Org-Id": other_org_id}
    )
    assert res.status_code == 403

def test_19_transaction_rollback(test_agent, test_org, monkeypatch):
    original_commit = Session.commit
    
    def mock_commit(self):
        if any(type(obj).__name__ == "BehavioralEvidence" for obj in self.new):
            raise Exception("Simulated DB Failure")
        original_commit(self)

    monkeypatch.setattr('sqlalchemy.orm.Session.commit', mock_commit)

    try:
        client.post(
            f"/agents/{test_agent.id}/trust/evidence",
            json={"outcome": "success", "evidence_quality": 1.0, "informative_value": 1.0},
            headers={"X-Mock-Principal-Org-Id": str(test_org.id)}
        )
    except Exception as e:
        assert "Simulated DB Failure" in str(e)

    trust_res = client.get(f"/agents/{test_agent.id}/trust", headers={"X-Mock-Principal-Org-Id": str(test_org.id)})
    data = trust_res.json()
    assert math.isclose(data["positive_evidence"], 0.0, abs_tol=1e-5)

