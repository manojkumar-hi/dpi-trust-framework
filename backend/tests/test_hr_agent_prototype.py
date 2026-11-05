from datetime import date, timedelta

import pytest

from app.core.policies import POLICY_CATALOG
from app.services.agent_templates.hr_agent import (
    calculate_leave_balance,
    check_leave_status,
    read_policies,
    submit_leave_request,
    view_employee_profile,
    view_holiday_calendar,
)
from app.services.agent_adapters.template_adapter import AgentTemplateAdapter
from app.services.authorization_engine import AuthorizationEngine


@pytest.mark.asyncio
async def test_each_hr_tool_returns_local_prototype_data():
    policies = await read_policies()
    balance = await calculate_leave_balance("EMP-1001")
    holidays = await view_holiday_calendar(2027)
    status = await check_leave_status("LR-2026-001")
    profile = await view_employee_profile("EMP-1001")

    assert policies["prototype"] is True and policies["policies"]
    assert balance["annual_days_remaining"] == 12
    assert holidays["year"] == 2027 and len(holidays["holidays"]) == 3
    assert status["status"] == "APPROVED"
    assert profile["profile"]["work_email"].endswith(".test")


@pytest.mark.asyncio
async def test_submit_leave_is_process_local_and_status_can_be_checked():
    start = date.today() + timedelta(days=3)
    end = start + timedelta(days=1)
    result = await submit_leave_request("EMP-1001", start, end, "Sample request for testing")
    status = await check_leave_status(result["request_id"])

    assert result["prototype"] is True
    assert result["status"] == "SUBMITTED (sample only)"
    assert "no HR system was contacted" in result["notice"]
    assert status["request_id"] == result["request_id"]


@pytest.mark.asyncio
async def test_unknown_sample_employee_does_not_return_real_data():
    result = await view_employee_profile("not-a-sample-id")
    assert result["prototype"] is True
    assert result["error"] == "No sample employee matches that ID."


def test_hr_policies_require_matching_allowlisted_delegation_capability():
    capabilities = {rule.action for rule in POLICY_CATALOG if rule.action.startswith("hr.")}
    assert len(capabilities) == 6
    for capability in capabilities:
        rule = next(rule for rule in POLICY_CATALOG if rule.resource_type == "agent" and rule.action == capability)
        assert rule.requires_delegation is True
        assert rule.required_capability == capability
        decision = AuthorizationEngine.evaluate({
            "subject": {"identity_status": "active", "trust": {"t": 0.5, "u": 1.0, "rr": 0.0}},
            "action": {"name": capability},
            "resource": {"type": "agent"},
            "delegation": {"is_present": True, "is_valid": True, "capabilities": [capability]},
        })
        assert decision.is_allowed is True
        denied = AuthorizationEngine.evaluate({
            "subject": {"identity_status": "active", "trust": {"t": 0.5, "u": 1.0, "rr": 0.0}},
            "action": {"name": capability},
            "resource": {"type": "agent"},
            "delegation": {"is_present": True, "is_valid": True, "capabilities": []},
        })
        assert denied.is_allowed is False
        assert denied.reason_code == "CAPABILITY_DENIED"

        if capability == "hr.submit_leave_request":
            low_trust = AuthorizationEngine.evaluate({
                "subject": {"identity_status": "active", "trust": {"t": 0.49, "u": 1.0, "rr": 0.0}},
                "action": {"name": capability},
                "resource": {"type": "agent"},
                "delegation": {"is_present": True, "is_valid": True, "capabilities": [capability]},
            })
            assert low_trust.is_allowed is False
            assert low_trust.reason_code == "TRUST_BELOW_THRESHOLD"


@pytest.mark.asyncio
async def test_template_adapter_dispatches_hr_tool_and_returns_execution_result():
    from types import SimpleNamespace
    from uuid import uuid4
    from unittest.mock import MagicMock

    target_agent_id = uuid4()
    db = MagicMock()
    db.get.return_value = SimpleNamespace(template_id="hr_agent")
    adapter = AgentTemplateAdapter()

    result = await adapter.execute_action(target_agent_id, "hr.read_policies", {}, db)

    assert result.status == "SUCCESS"
    assert result.data["result"]["prototype"] is True
    assert result.data["result"]["policies"]
