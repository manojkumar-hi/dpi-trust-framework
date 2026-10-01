import os
import json
import jwt
import time
import base64
from typing import Type, Any, Optional
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from pydantic import BaseModel, PrivateAttr, Field

from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_groq import ChatGroq

from app.models.agent_identity import AgentIdentity
from app.models.agent_identity_key import AgentIdentityKey
from app.models.agent import Agent
from app.models.organization import Organization
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.verifiable_credential import VerifiableCredential
from app.models.challenge import Challenge
from app.models.agent_trust_state import AgentTrustState
from app.models.agent_action_log import AgentActionLog
from app.models.audit_record import AuditRecord

from app.main import app
from app.database.connection import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import Base

from fastapi.testclient import TestClient

# ----------------- DPIToolWrapper -----------------

class DPIToolWrapper(BaseTool):
    name: str = "langchain.tool.add"
    description: str = "Adds two integers together."
    # We will let the tool define its args using LangChain's inferencing if we define the args_schema
    # but since we want to be minimal, we just accept a dict
    
    # Internal fields for connecting to DPI
    _test_client: Any = PrivateAttr()
    _vp_jwt: str = PrivateAttr()
    _challenge_id: str = PrivateAttr()
    _target_agent_did: str = PrivateAttr()
    _source_agent_did: str = PrivateAttr()
    
    def __init__(self, test_client: Any, vp_jwt: str, challenge_id: str, target_agent_did: str, source_agent_did: str, **kwargs):
        super().__init__(**kwargs)
        self._test_client = test_client
        self._vp_jwt = vp_jwt
        self._challenge_id = challenge_id
        self._target_agent_did = target_agent_did
        self._source_agent_did = source_agent_did

    def _run(self, a: int, b: int) -> str:
        payload = {"a": a, "b": b}
        
        request_data = {
            "challenge_id": self._challenge_id,
            "source_agent_did": self._source_agent_did,
            "target_agent_did": self._target_agent_did,
            "action_type": self.name,
            "resource_id": "none",
            "payload": payload,
            "delegation_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "authentication_proof": {
                "type": "VerifiablePresentation",
                "vp_jwt": self._vp_jwt
            }
        }
        
        headers = {"Idempotency-Key": str(uuid4())}
        response = self._test_client.post("/gateway/action", json=request_data, headers=headers)
        
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get("status") == "SUCCESS":
                return str(result_data["result"].get("result"))
        
        return f"Error {response.status_code}: {response.text}"


# ----------------- Test Setup -----------------

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

@pytest.fixture
def client(override_get_db):
    return TestClient(app)

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
    # Clean up any existing data in the shared memory DB (since SQLite in memory is shared here)
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    
    org = Organization(name="Test Org LLM", domain=f"test-llm-{uuid4()}.org")
    db.add(org)
    db.commit()

    org_did = f"did:web:test-llm.org:{org.id}"
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

    agent = Agent(organization_id=org.id, name="Test Agent LLM", agent_type="Service")
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

    # Target Agent
    target_agent = Agent(organization_id=org.id, name="Target Agent", agent_type="Service")
    db.add(target_agent)
    db.commit()
    target_agent_did = f"{org_did}:agents:{target_agent.id}"
    
    target_agent_ident = AgentIdentity(agent_id=target_agent.id, did=target_agent_did, public_key="fake")
    db.add(target_agent_ident)
    db.commit()

    # Agent Trust State (Needs to be high enough for the low-risk action)
    trust_state = AgentTrustState(
        agent_id=agent.id,
        positive_evidence_r=18.0,
        negative_evidence_s=0.0,
        current_window_r=0.0,
        current_window_start=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc)
    )
    db.add(trust_state)
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
                "agent_name": "Test Agent LLM"
            }
        }
    }
    vc_jwt = jwt.encode(vc_payload, org_priv, algorithm="EdDSA", headers={"kid": org_key.verification_method})

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
        "agent_id": agent.id,
        "org_did": org_did,
        "agent_did": agent_did,
        "agent_priv": agent_priv,
        "agent_kid": agent_key.verification_method,
        "vc_jwt": vc_jwt,
        "target_agent_did": target_agent_did
    }

def create_valid_vp_jwt(test_setup, challenge_nonce: str):
    now = int(time.time())
    vp_payload = {
        "iss": test_setup["agent_did"],
        "aud": "did:web:trust.dpi.local",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": str(uuid4()),
        "nonce": challenge_nonce,
        "vp": {
            "@context": ["https://www.w3.org/2018/credentials/v1"],
            "type": ["VerifiablePresentation"],
            "verifiableCredential": [test_setup["vc_jwt"]]
        }
    }
    return jwt.encode(vp_payload, test_setup["agent_priv"], algorithm="EdDSA", headers={"kid": test_setup["agent_kid"]})

# ----------------- Helper Functions -----------------

def run_agent_loop(llm, tool, prompt: str):
    llm_with_tools = llm.bind_tools([tool])
    messages = [HumanMessage(content=prompt)]
    
    # Run LLM
    response = llm_with_tools.invoke(messages)
    messages.append(response)
    
    # Check if tool was called
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            # We execute the tool directly for this minimal loop
            if tool_call["name"] == tool.name:
                tool_msg = tool.invoke(tool_call)
                messages.append(tool_msg)
        
        # Second LLM call
        final_response = llm_with_tools.invoke(messages)
        messages.append(final_response)
        return final_response.content
    return response.content

# ----------------- Path A: Deterministic Mock Test -----------------

class MockChatOpenAI(BaseModel):
    """A mock LLM that always returns a tool call for the first invocation, then a final answer."""
    def bind_tools(self, tools):
        return self
        
    def invoke(self, messages):
        if len(messages) == 1:
            # First call, return a tool call
            return AIMessage(
                content="",
                tool_calls=[{"name": "langchain.tool.add", "args": {"a": 10, "b": 15}, "id": "call_123"}]
            )
        else:
            # Second call, extract result and return final message
            tool_msg = [m for m in messages if isinstance(m, ToolMessage)][0]
            return AIMessage(content=f"The answer is {tool_msg.content}")

def test_deterministic_llm_integration(test_setup, client, monkeypatch):
    """
    PATH A - Deterministic integration test using a mocked LLM.
    Proves the full DPI boundary, Gateway, and Adapter execute properly.
    """
    db = test_setup["db"]
    
    # 1. Get Challenge
    from app.services.vp_auth_service import create_challenge
    challenge = create_challenge(db)
    
    # 2. Create VP
    vp_jwt = create_valid_vp_jwt(test_setup, challenge.nonce)
    
    # 3. Setup DPIToolWrapper
    tool = DPIToolWrapper(
        test_client=client,
        vp_jwt=vp_jwt,
        challenge_id=str(challenge.id),
        target_agent_did=test_setup["target_agent_did"],
        source_agent_did=test_setup["agent_did"]
    )
    
    # 4. Run Agent with Mock LLM
    mock_llm = MockChatOpenAI()
    final_content = run_agent_loop(mock_llm, tool, "Calculate 10 + 15 using the available tool.")
    
    # 5. Assertions
    assert "25" in final_content
    
    # Check DB logs
    action_log = db.query(AgentActionLog).filter_by(source_agent_id=test_setup["agent_id"]).first()
    assert action_log is not None
    assert action_log.status == "SUCCESS"
    assert action_log.action_type == "langchain.tool.add"
    
    # Check Audit
    audit_record = db.query(AuditRecord).filter_by(event_type="action_executed").first()
    assert audit_record is not None


def test_deterministic_negative_integration(test_setup, client):
    """
    PATH A - Negative deterministic integration test.
    Low trust causes authorization failure.
    """
    db = test_setup["db"]
    
    from app.models.behavioral_evidence import BehavioralEvidence
    
    # Sabotage the trust to increase recent risk to 1.0
    evidence = BehavioralEvidence(
        agent_id=test_setup["agent_id"],
        timestamp=datetime.now(timezone.utc),
        outcome="failure",
        severity=16.0,
        evidence_quality=1.0,
        informative_value=1.0,
        action_metadata={"simulated": "failure"},
        created_at=datetime.now(timezone.utc)
    )
    db.add(evidence)
    db.commit()
    
    # 1. Get Challenge
    from app.services.vp_auth_service import create_challenge
    challenge = create_challenge(db)
    
    # 2. Create VP
    vp_jwt = create_valid_vp_jwt(test_setup, challenge.nonce)
    
    # 3. Setup DPIToolWrapper
    tool = DPIToolWrapper(
        test_client=client,
        vp_jwt=vp_jwt,
        challenge_id=str(challenge.id),
        target_agent_did=test_setup["target_agent_did"],
        source_agent_did=test_setup["agent_did"]
    )
    
    # 4. Run Agent with Mock LLM
    mock_llm = MockChatOpenAI()
    final_content = run_agent_loop(mock_llm, tool, "Calculate 10 + 15 using the available tool.")
    
    # 5. Assertions - The tool should return the HTTP 403 string
    assert "Error 403" in final_content
    
    # Verify DB state reflects denial
    action_log = db.query(AgentActionLog).filter_by(source_agent_id=test_setup["agent_id"]).first()
    assert action_log is not None
    assert action_log.status == "DENIED"
    
    audit_record = db.query(AuditRecord).filter_by(event_type="action_denied").first()
    assert audit_record is not None


# ----------------- Path B: Live LLM Integration -----------------

@pytest.mark.skipif("GROQ_API_KEY" not in os.environ, reason="Requires real GROQ_API_KEY")
def test_live_llm_integration(test_setup, client):
    """
    PATH B - Live integration test using a real ChatGroq LLM.
    Requires GROQ_API_KEY to be set in the environment.
    """
    db = test_setup["db"]
    
    from app.services.vp_auth_service import create_challenge
    challenge = create_challenge(db)
    
    vp_jwt = create_valid_vp_jwt(test_setup, challenge.nonce)
    
    tool = DPIToolWrapper(
        test_client=client,
        vp_jwt=vp_jwt,
        challenge_id=str(challenge.id),
        target_agent_did=test_setup["target_agent_did"],
        source_agent_did=test_setup["agent_did"]
    )
    
    llm = ChatGroq(model="qwen/qwen3.8-27b", temperature=0) # Using a generally available groq model
    
    prompt = "You are a helpful assistant. Please calculate 12 + 37 using the tools you have available."
    final_content = run_agent_loop(llm, tool, prompt)
    
    # Ensure the LLM used the tool and got the correct answer
    assert "49" in final_content
    
    # Ensure DPI logged it
    action_log = db.query(AgentActionLog).filter_by(source_agent_id=test_setup["agent_id"]).first()
    assert action_log is not None
    assert action_log.status == "SUCCESS"
