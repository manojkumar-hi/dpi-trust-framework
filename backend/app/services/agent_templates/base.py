from typing import Callable, Any
from pydantic import BaseModel, Field

class AgentTemplateTool(BaseModel):
    name: str
    description: str
    capability_code: str
    func: Callable[..., Any]

class AgentTemplate(BaseModel):
    template_id: str
    template_version: str
    display_name: str
    description: str
    system_prompt: str
    tools: list[AgentTemplateTool]

    @property
    def supported_capabilities(self) -> list[str]:
        return [tool.capability_code for tool in self.tools]
