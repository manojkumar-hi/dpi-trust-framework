import pytest
import uuid
from typing import Dict, Any

from app.services.agent_adapters.base import AgentRuntimeAdapter, AgentExecutionResult
from app.services.agent_adapters.registry import AgentRuntimeRegistry
from app.services.agent_adapters.native_adapter import NativeAgentReadAdapter
from app.services.agent_adapters.langchain_adapter import LangchainAdapter

@pytest.fixture
def test_registry():
    registry = AgentRuntimeRegistry()
    registry.register_adapter(NativeAgentReadAdapter())
    registry.register_adapter(LangchainAdapter())
    return registry

@pytest.mark.asyncio
async def test_registry_finds_correct_adapter(test_registry):
    adapter = await test_registry.get_adapter_for("agent.read", {})
    assert isinstance(adapter, NativeAgentReadAdapter)
    
    adapter2 = await test_registry.get_adapter_for("langchain.tool.add", {})
    assert isinstance(adapter2, LangchainAdapter)

@pytest.mark.asyncio
async def test_unsupported_action_is_rejected(test_registry):
    adapter = await test_registry.get_adapter_for("unknown.action", {})
    assert adapter is None

@pytest.mark.asyncio
async def test_langchain_tool_executes(test_registry):
    adapter = await test_registry.get_adapter_for("langchain.tool.add", {})
    assert adapter is not None
    
    result = await adapter.execute_action(
        target_agent_id=uuid.uuid4(),
        action_type="langchain.tool.add",
        payload={"a": 5, "b": 3}
    )
    
    assert result.status == "SUCCESS"
    assert result.data["result"] == 8

@pytest.mark.asyncio
async def test_langchain_tool_arguments_validated(test_registry):
    adapter = await test_registry.get_adapter_for("langchain.tool.add", {})
    assert adapter is not None
    
    result = await adapter.execute_action(
        target_agent_id=uuid.uuid4(),
        action_type="langchain.tool.add",
        payload={"a": 5, "b": "invalid"}  # Type mismatch
    )
    
    assert result.status == "FAILURE"
    assert "Tool execution failed" in result.error
    assert "validation error" in result.error.lower() or "input" in result.error.lower()

