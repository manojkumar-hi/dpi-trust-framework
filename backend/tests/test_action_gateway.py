import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.services.action_orchestrator_service import ActionOrchestratorService
from app.models.agent_action_log import AgentActionLog
from app.models.agent_identity import AgentIdentity
from app.models.agent import Agent
from app.schemas.trust import TrustScoreResponse

client = TestClient(app)

@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)

@patch("app.api.action_gateway.ActionOrchestratorService.execute_action")
def test_gateway_action_success(mock_execute):
    mock_execute.return_value = {
        "execution_id": "test-exec-123",
        "status": "SUCCESS",
        "result": {"message": "Success"}
    }
    
    response = client.post("/gateway/action", json={
        "challenge_id": str(uuid4()),
        "source_agent_did": "did:web:agent-a",
        "target_agent_did": "did:web:agent-b",
        "action_type": "agent.read",
        "resource_id": "agent-b-uuid",
        "payload": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "authentication_proof": {
            "type": "VerifiablePresentation",
            "vp_jwt": "fake.jwt.token"
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["execution_id"] == "test-exec-123"

@pytest.mark.asyncio
@patch("app.services.action_orchestrator_service.verify_vp_and_consume_challenge")
@patch("app.services.action_orchestrator_service.TrustService.get_trust_score")
@patch("app.services.action_orchestrator_service.TrustService.ingest_evidence")
async def test_action_orchestrator_success(mock_ingest, mock_trust, mock_verify, mock_db):
    # Mocking VP auth
    agent_identity = AgentIdentity(did="did:web:agent-a", agent_id=uuid4(), agent=Agent(organization_id=uuid4()), status="active")
    mock_verify.return_value = agent_identity
    
    # Mocking Trust (high enough for basic read)
    mock_trust.return_value = TrustScoreResponse(
        agent_id=agent_identity.agent_id,
        trust=0.9,
        belief=0.9,
        disbelief=0.0,
        uncertainty=0.1,
        recent_risk=0.0,
        positive_evidence=10.0,
        negative_evidence=0.0
    )
    
    # Mock DB scalar for target agent
    target_agent = Agent(id=uuid4(), organization_id=uuid4(), name="Agent B", agent_type="Test", status="ACTIVE")
    mock_db.scalar.return_value = target_agent
    
    result = await ActionOrchestratorService.execute_action(
        db=mock_db,
        challenge_id=uuid4(),
        vp_jwt="fake",
        target_agent_did="did:web:agent-b",
        action_type="agent.read",
        resource_id="agent-b-uuid",
        payload={}
    )
    
    assert result["status"] == "SUCCESS"
    assert "execution_id" in result
    mock_db.add.assert_called()
    mock_ingest.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.action_orchestrator_service.verify_vp_and_consume_challenge")
@patch("app.services.action_orchestrator_service.TrustService.get_trust_score")
@patch("app.services.action_orchestrator_service.TrustService.ingest_evidence")
@patch("app.services.agent_adapters.registry.AgentRuntimeRegistry.get_adapter_for")
async def test_action_orchestrator_denied(mock_get_adapter, mock_ingest, mock_trust, mock_verify, mock_db):
    # Mocking VP auth
    agent_identity = AgentIdentity(did="did:web:agent-a", agent_id=uuid4(), agent=Agent(organization_id=uuid4()), status="active")
    mock_verify.return_value = agent_identity
    
    # Mocking Trust (too low for VC issue)
    mock_trust.return_value = TrustScoreResponse(
        agent_id=agent_identity.agent_id,
        trust=0.1,  # VC issue requires 0.8
        belief=0.1, disbelief=0.5, uncertainty=0.4, recent_risk=0.5, positive_evidence=0.0, negative_evidence=10.0
    )
    
    target_agent = Agent(id=uuid4(), organization_id=uuid4(), name="Agent B", agent_type="Test", status="ACTIVE")
    mock_db.scalar.return_value = target_agent
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await ActionOrchestratorService.execute_action(
            db=mock_db,
            challenge_id=uuid4(),
            vp_jwt="fake",
            target_agent_did="did:web:agent-b",
            action_type="verifiable_credential.issue",
            resource_id="agent-b-uuid",
            payload={}
        )
    
    assert excinfo.value.status_code == 403
    mock_get_adapter.assert_not_called()  # Never reaches adapter
    mock_ingest.assert_not_called()       # No positive evidence

@pytest.mark.asyncio
@patch("app.services.action_orchestrator_service.verify_vp_and_consume_challenge")
@patch("app.services.action_orchestrator_service.TrustService.get_trust_score")
@patch("app.services.action_orchestrator_service.TrustService.ingest_evidence")
@patch("app.services.agent_adapters.registry.AgentRuntimeRegistry.get_adapter_for")
async def test_action_orchestrator_adapter_failure(mock_get_adapter, mock_ingest, mock_trust, mock_verify, mock_db):
    # Mocking VP auth
    agent_identity = AgentIdentity(did="did:web:agent-a", agent_id=uuid4(), agent=Agent(organization_id=uuid4()), status="active")
    mock_verify.return_value = agent_identity
    
    mock_trust.return_value = TrustScoreResponse(
        agent_id=agent_identity.agent_id,
        trust=0.9, belief=0.9, disbelief=0.0, uncertainty=0.1, recent_risk=0.0, positive_evidence=10.0, negative_evidence=0.0
    )
    
    target_agent = Agent(id=uuid4(), organization_id=uuid4(), name="Agent B", agent_type="Test", status="ACTIVE")
    mock_db.scalar.return_value = target_agent
    
    # Mock adapter failure
    from unittest.mock import AsyncMock
    mock_adapter = AsyncMock()
    from app.services.agent_adapters.base import AgentExecutionResult
    mock_adapter.execute_action.return_value = AgentExecutionResult(status="FAILURE", error="Simulated failure")
    mock_get_adapter.return_value = mock_adapter
    
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        await ActionOrchestratorService.execute_action(
            db=mock_db,
            challenge_id=uuid4(),
            vp_jwt="fake",
            target_agent_did="did:web:agent-b",
            action_type="agent.read",
            resource_id="agent-b-uuid",
            payload={}
        )
    
    assert excinfo.value.status_code == 500
    assert "Simulated failure" in excinfo.value.detail
    mock_get_adapter.assert_called_once()
    mock_adapter.execute_action.assert_called_once()
    mock_ingest.assert_not_called()  # No positive evidence on failure
@pytest.mark.asyncio
@patch("app.services.action_orchestrator_service.verify_vp_and_consume_challenge")
@patch("app.services.action_orchestrator_service.TrustService.get_trust_score")
@patch("app.services.action_orchestrator_service.TrustService.ingest_evidence")
async def test_action_orchestrator_langchain_success(mock_ingest, mock_trust, mock_verify, mock_db):
    # Mocking VP auth
    agent_identity = AgentIdentity(did="did:web:agent-a", agent_id=uuid4(), agent=Agent(organization_id=uuid4()), status="active")
    mock_verify.return_value = agent_identity
    
    mock_trust.return_value = TrustScoreResponse(
        agent_id=agent_identity.agent_id,
        trust=0.9, belief=0.9, disbelief=0.0, uncertainty=0.1, recent_risk=0.0, positive_evidence=10.0, negative_evidence=0.0
    )
    
    target_agent = Agent(id=uuid4(), organization_id=uuid4(), name="Agent B", agent_type="Test", status="ACTIVE")
    mock_db.scalar.return_value = target_agent
    
    result = await ActionOrchestratorService.execute_action(
        db=mock_db,
        challenge_id=uuid4(),
        vp_jwt="fake",
        target_agent_did="did:web:agent-b",
        action_type="langchain.tool.add",
        resource_id="math-1",
        payload={"a": 10, "b": 15}
    )
    
    assert result["status"] == "SUCCESS"
    assert result["result"]["result"] == 25
    assert "execution_id" in result
    mock_db.add.assert_called()
    mock_ingest.assert_called_once()
