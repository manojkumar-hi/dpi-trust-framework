from typing import List, Dict, Any, Optional
from .base import AgentRuntimeAdapter

class AgentRuntimeRegistry:
    def __init__(self):
        self._adapters: List[AgentRuntimeAdapter] = []

    def register_adapter(self, adapter: AgentRuntimeAdapter):
        self._adapters.append(adapter)

    async def get_adapter_for(self, action_type: str, payload: Dict[str, Any]) -> Optional[AgentRuntimeAdapter]:
        for adapter in self._adapters:
            if await adapter.can_handle(action_type, payload):
                return adapter
        return None

# Global registry instance to inject/use
registry = AgentRuntimeRegistry()
