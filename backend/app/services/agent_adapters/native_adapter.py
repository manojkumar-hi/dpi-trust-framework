from typing import Any, Dict
import uuid
from .base import AgentRuntimeAdapter, AgentExecutionResult

class NativeAgentReadAdapter(AgentRuntimeAdapter):
    """
    Adapter that preserves the existing `agent.read` functionality natively
    without requiring an external LLM agent framework.
    """
    def __init__(self, db_session=None):
        self.db = db_session
        
    async def can_handle(self, action_type: str, payload: Dict[str, Any]) -> bool:
        return action_type == "agent.read"
        
    async def execute_action(
        self,
        target_agent_id: uuid.UUID,
        action_type: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> AgentExecutionResult:
        db = kwargs.get("db")
        if not db:
            return AgentExecutionResult(status="FAILURE", error="Database session not provided in context")
            
        from app.models.agent import Agent
        target_agent = db.scalar(
            __import__('sqlalchemy').select(Agent).where(Agent.id == target_agent_id)
        )
        if not target_agent:
            return AgentExecutionResult(status="FAILURE", error="Target agent not found")
            
        result = {
            "id": str(target_agent.id),
            "organization_id": str(target_agent.organization_id),
            "name": target_agent.name,
            "agent_type": target_agent.agent_type,
            "status": target_agent.status
        }
        
        return AgentExecutionResult(status="SUCCESS", data=result)
