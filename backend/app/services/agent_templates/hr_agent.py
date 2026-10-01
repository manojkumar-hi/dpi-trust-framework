from app.services.agent_templates.base import AgentTemplate, AgentTemplateTool

async def read_hr_policies() -> str:
    """Reads the HR policies"""
    return "HR Policies: 1. Be nice. 2. Work hard."

async def calculate_leave_balance(employee_id: str) -> str:
    """Calculates leave balance for an employee"""
    return f"Leave balance for {employee_id} is 15 days."

hr_agent_template = AgentTemplate(
    template_id="hr_agent",
    template_version="1.0.0",
    display_name="HR Agent",
    description="Domain agent for Human Resources operations.",
    system_prompt="You are a helpful HR assistant. You can read policies and calculate leave balances.",
    tools=[
        AgentTemplateTool(
            name="read_hr_policies",
            description="Reads the standard HR policies",
            capability_code="hr.read_policies",
            func=read_hr_policies
        ),
        AgentTemplateTool(
            name="calculate_leave_balance",
            description="Calculates the leave balance for a given employee ID",
            capability_code="hr.calculate_leave_balance",
            func=calculate_leave_balance
        )
    ]
)
