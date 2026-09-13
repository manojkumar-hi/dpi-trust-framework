import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

from app.database.base import Base
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.services.auth_binding_service import resolve_identity_binding
from app.core.auth import AuthError, IDENTITY_NOT_FOUND, IDENTITY_REVOKED, IDENTITY_AMBIGUOUS, IDENTITY_MISMATCH

# Create in-memory sqlite
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def active_org(db):
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        domain="test.com",
        status="active"
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

@pytest.fixture
def active_org_identity(db, active_org):
    identity = OrganizationIdentity(
        organization_id=active_org.id,
        did="did:test:org",
        public_key="pubkey",
        authentication_issuer="https://auth.test",
        authentication_subject="org-sub-1",
        status="active"
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity

@pytest.fixture
def active_agent(db, active_org):
    agent = Agent(
        id=uuid.uuid4(),
        organization_id=active_org.id,
        name="Test Agent",
        agent_type="system",
        status="active"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

@pytest.fixture
def active_agent_identity(db, active_agent):
    identity = AgentIdentity(
        agent_id=active_agent.id,
        did="did:test:agent",
        public_key="pubkey",
        authentication_issuer="https://auth.test",
        authentication_subject="agent-sub-1",
        status="active"
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def test_resolve_agent_identity_success(db, active_agent_identity, active_agent):
    principal = resolve_identity_binding(db, "https://auth.test", "agent-sub-1")
    assert principal.agent_id == active_agent.id
    assert principal.organization_id == active_agent.organization_id
    # Principal.subject MUST equal the JWT sub exactly
    assert principal.subject == "agent-sub-1"

def test_resolve_org_identity_success(db, active_org_identity, active_org):
    principal = resolve_identity_binding(db, "https://auth.test", "org-sub-1")
    assert principal.agent_id is None
    assert principal.organization_id == active_org.id
    # Principal.subject MUST equal the JWT sub exactly
    assert principal.subject == "org-sub-1"

def test_resolve_ambiguous_identity(db, active_org_identity, active_agent_identity):
    # Make them match
    active_agent_identity.authentication_subject = "org-sub-1"
    db.commit()
    
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "org-sub-1")
    assert exc.value.code == IDENTITY_AMBIGUOUS

def test_hints_correct_org_id(db, active_org_identity, active_org):
    principal = resolve_identity_binding(db, "https://auth.test", "org-sub-1", dpi_org_id=str(active_org.id))
    assert principal.organization_id == active_org.id

def test_hints_incorrect_org_id(db, active_org_identity, active_org):
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "org-sub-1", dpi_org_id=str(uuid.uuid4()))
    assert exc.value.code == IDENTITY_MISMATCH

def test_hints_correct_agent_id(db, active_agent_identity, active_agent):
    principal = resolve_identity_binding(db, "https://auth.test", "agent-sub-1", dpi_agent_id=str(active_agent.id))
    assert principal.agent_id == active_agent.id

def test_hints_incorrect_agent_id(db, active_agent_identity, active_agent):
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "agent-sub-1", dpi_agent_id=str(uuid.uuid4()))
    assert exc.value.code == IDENTITY_MISMATCH

def test_hints_agent_id_for_org_identity(db, active_org_identity):
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "org-sub-1", dpi_agent_id=str(uuid.uuid4()))
    assert exc.value.code == IDENTITY_MISMATCH

def test_resolve_agent_identity_revoked_identity(db, active_agent_identity):
    active_agent_identity.status = "revoked"
    db.commit()
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "agent-sub-1")
    assert exc.value.code == IDENTITY_REVOKED

def test_resolve_agent_identity_revoked_agent(db, active_agent_identity, active_agent):
    active_agent.status = "revoked"
    db.commit()
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "agent-sub-1")
    assert exc.value.code == IDENTITY_REVOKED

def test_resolve_org_identity_revoked_identity(db, active_org_identity):
    active_org_identity.status = "revoked"
    db.commit()
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "org-sub-1")
    assert exc.value.code == IDENTITY_REVOKED

def test_resolve_org_identity_revoked_org(db, active_org_identity, active_org):
    active_org.status = "suspended"
    db.commit()
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "org-sub-1")
    assert exc.value.code == IDENTITY_REVOKED

def test_resolve_identity_not_found(db):
    with pytest.raises(AuthError) as exc:
        resolve_identity_binding(db, "https://auth.test", "non-existent")
    assert exc.value.code == IDENTITY_NOT_FOUND
