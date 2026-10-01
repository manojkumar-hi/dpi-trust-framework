from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import uuid

class AgentExecutionResult:
    def __init__(self, status: str, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """
        status: 'SUCCESS' or 'FAILURE'
        """
        self.status = status
        self.data = data or {}
        self.error = error

class AgentRuntimeAdapter(ABC):
    @abstractmethod
    async def can_handle(self, action_type: str, payload: Dict[str, Any]) -> bool:
        """Return True if this adapter supports the given action_type and payload."""
        pass
        
    @abstractmethod
    async def execute_action(
        self,
        target_agent_id: uuid.UUID,
        action_type: str,
        payload: Dict[str, Any],
        **kwargs
    ) -> AgentExecutionResult:
        """Execute the real action and return a structured result."""
        pass
