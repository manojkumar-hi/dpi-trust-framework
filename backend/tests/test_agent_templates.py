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
    expected_capabilities = {
        "hr.read_policies",
        "hr.calculate_leave_balance",
        "hr.view_holiday_calendar",
        "hr.check_leave_status",
        "hr.submit_leave_request",
        "hr.view_employee_profile",
        "hr.plan_training_program",
    }
    assert set(template.supported_capabilities) == expected_capabilities
    
    # Verify tools exist
    tools = {t.name: t for t in template.tools}
    assert "read_hr_policies" in tools
    assert tools["read_hr_policies"].capability_code == "hr.read_policies"
    assert len(tools) == len(expected_capabilities)


@pytest.mark.asyncio
async def test_hr_training_plan_contains_budget_context():
    from app.services.agent_templates.hr_agent import plan_training_program

    result = await plan_training_program(
        department="Customer Support",
        training_topic="Service quality",
        budget={"cost_center": "CC-100", "remaining": "101500.00", "currency": "USD"},
    )

    assert result["workflow"] == "workforce_training_program"
    assert result["budget_summary"]["remaining"] == "101500.00"
    assert result["training_plan"]["audience"] == "Customer Support team"
