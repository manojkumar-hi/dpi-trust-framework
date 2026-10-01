from typing import Any, Dict
import uuid
from .base import AgentRuntimeAdapter, AgentExecutionResult

from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b

class LangchainAdapter(AgentRuntimeAdapter):
    """
    Minimal LangChain adapter that can execute a predefined LangChain tool.
    """
    def __init__(self):
        self.tools = {
            "langchain.tool.add": add
        }

    async def can_handle(self, action_type: str, payload: Dict[str, Any]) -> bool:
        return action_type in self.tools

    async def execute_action(
        self,
        target_agent_id: uuid.UUID,
        action_type: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> AgentExecutionResult:
        if action_type not in self.tools:
            return AgentExecutionResult(status="FAILURE", error=f"Action {action_type} not supported by LangchainAdapter")
            
        tool_instance = self.tools[action_type]
        
        # Strict input validation via Pydantic on LangChain tool
        try:
            result = tool_instance.invoke(payload)
            return AgentExecutionResult(status="SUCCESS", data={"result": result})
        except Exception as e:
            return AgentExecutionResult(status="FAILURE", error=f"Tool execution failed: {str(e)}")
