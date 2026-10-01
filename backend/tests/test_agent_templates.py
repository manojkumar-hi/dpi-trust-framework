import pytest
from app.services.agent_templates.registry import get_template, list_templates, register_template
from app.services.agent_templates.base import AgentTemplate, AgentTemplateTool

def test_template_registry_lookup():
    template = get_template("hr_agent")
    assert template is not None
    assert template.template_id == "hr_agent"
    assert template.template_version == "1.0.0"

def test_template_registry_list():
    templates = list_templates()
    assert len(templates) >= 1
    assert any(t.template_id == "hr_agent" for t in templates)

def test_template_capabilities():
    template = get_template("hr_agent")
    assert "hr.read_policies" in template.supported_capabilities
    assert "hr.calculate_leave_balance" in template.supported_capabilities
    
    # Verify tools exist
    tools = {t.name: t for t in template.tools}
    assert "read_hr_policies" in tools
    assert tools["read_hr_policies"].capability_code == "hr.read_policies"
