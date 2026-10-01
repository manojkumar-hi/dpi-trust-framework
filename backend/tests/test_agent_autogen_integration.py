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

from app.api.dependencies import Principal, get_current_principal
from fastapi import Request

@pytest.fixture(autouse=True)
def override_principal_dependency():
    def _override(request: Request):
        mock_org_id = request.headers.get("X-Mock-Principal-Org-Id")
        if mock_org_id:
            from uuid import UUID
            return Principal(organization_id=UUID(mock_org_id))
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing mock header")
    app.dependency_overrides[get_current_principal] = _override
    yield
    app.dependency_overrides.pop(get_current_principal, None)

from fastapi.testclient import TestClient


from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool
from autogen_ext.models.openai import OpenAIChatCompletionClient
import dotenv
dotenv.load_dotenv()
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


def build_dpi_autogen_tool(client, vp_jwt: str, challenge_id: str, source_agent_did: str, target_agent_did: str):
    async def dpi_math_add(a: int, b: int) -> str:
        """Adds two integers together securely via the DPI Gateway"""
        request_data = {
            "challenge_id": challenge_id,
            "source_agent_did": source_agent_did,
            "target_agent_did": target_agent_did,
            "action_type": "langchain.tool.add",  # Use the same action type to match DB setup
            "resource_id": "none",
            "payload": {"a": a, "b": b},
            "delegation_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "authentication_proof": {
                "type": "VerifiablePresentation",
                "vp_jwt": vp_jwt
            }
        }
        headers = {"Idempotency-Key": str(uuid4())}
        response = client.post("/gateway/action", json=request_data, headers=headers)
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get("status") == "SUCCESS":
                return str(result_data["result"].get("result", result_data["result"]))
            return f"Action failed: {result_data.get('error')}"
        return f"Error {response.status_code}: {response.text}"

    return FunctionTool(
        dpi_math_add,
        name="dpi_math_add",
        description="Adds two integers together securely via the DPI Gateway"
    )

# ----------------- Path B: Live LLM Integration -----------------

@pytest.mark.skipif("GROQ_API_KEY" not in os.environ, reason="Requires real GROQ_API_KEY")
@pytest.mark.asyncio
async def test_live_autogen_integration(test_setup, client):
    """
    PATH B - Live integration test using a real ChatGroq LLM via AutoGen.
    Requires GROQ_API_KEY to be set in the environment.
    """
    db = test_setup["db"]
    
    from app.services.vp_auth_service import create_challenge
    challenge = create_challenge(db)
    
    vp_jwt = create_valid_vp_jwt(test_setup, challenge.nonce)
    
    tool = build_dpi_autogen_tool(
        client=client,
        vp_jwt=vp_jwt,
        challenge_id=str(challenge.id),
        target_agent_did=test_setup["target_agent_did"],
        source_agent_did=test_setup["agent_did"]
    )
    
    model_client = OpenAIChatCompletionClient(
        model="qwen/qwen3.8-27b",
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": "unknown"
        }
    )
    
    agent = AssistantAgent(
        name="assistant",
        model_client=model_client,
        tools=[tool],
        system_message="You are a helpful assistant. Use the dpi_math_add tool to calculate 12 + 37. Output only the final answer."
    )
    
    result = await agent.run(task="Calculate 12 + 37 using the available tool.")
    print("\n[Agent Output]", result.messages)
    
    # Ensure DPI logged it
    action_log = db.query(AgentActionLog).filter_by(source_agent_id=test_setup["agent_id"]).first()
    assert action_log is not None
    assert action_log.status == "SUCCESS"
    assert action_log.action_type == "langchain.tool.add"

    from app.models.behavioral_evidence import BehavioralEvidence
    evidence = db.query(BehavioralEvidence).filter_by(action_log_id=action_log.id).first()
    assert evidence is not None

    audit = db.query(AuditRecord).filter_by(subject_agent_id=test_setup["agent_id"]).first()
    assert audit is not None
