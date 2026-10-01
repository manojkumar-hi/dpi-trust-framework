import inspect
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.services.agent_templates.registry import get_template, list_templates
from app.services.agent_adapters.base import AgentRuntimeAdapter, AgentExecutionResult

class AgentTemplateAdapter(AgentRuntimeAdapter):
    """
    Adapter that executes domain-specific tools defined in Agent Templates.
    It looks up the target agent's template, finds the matching tool by capability_code,
    and executes the underlying Python function.
    """

    async def can_handle(self, action_type: str, payload: Dict[str, Any]) -> bool:
        # We can handle it if any template defines a tool with this capability_code
        for template in list_templates():
            for tool in template.tools:
                if tool.capability_code == action_type:
                    return True
        return False

    async def execute_action(
        self, target_agent_id: UUID, action_type: str, payload: Dict[str, Any], db: Session
    ) -> AgentExecutionResult:
        agent = db.get(Agent, target_agent_id)
        if not agent or not agent.template_id:
            return AgentExecutionResult(status="FAILED", error="Target agent has no template")
        
        template = get_template(agent.template_id)
        if not template:
            return AgentExecutionResult(status="FAILED", error="Template not found")
            
        tool_def = None
        for t in template.tools:
            if t.capability_code == action_type:
                tool_def = t
                break
                
        if not tool_def:
            return AgentExecutionResult(status="FAILED", error=f"Tool for {action_type} not found in template")
            
        try:
            # Execute the python function
            if inspect.iscoroutinefunction(tool_def.func):
                result = await tool_def.func(**payload)
            else:
                result = tool_def.func(**payload)
            return AdapterExecutionResult(status="SUCCESS", data={"result": result})
        except Exception as e:
            return AdapterExecutionResult(status="FAILED", error=str(e))
