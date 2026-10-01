from app.services.agent_templates.base import AgentTemplate
from app.services.agent_templates.hr_agent import hr_agent_template

_registry: dict[str, AgentTemplate] = {}

def register_template(template: AgentTemplate) -> None:
    _registry[template.template_id] = template

def get_template(template_id: str) -> AgentTemplate | None:
    return _registry.get(template_id)

def list_templates() -> list[AgentTemplate]:
    return list(_registry.values())

# Register built-ins
register_template(hr_agent_template)
