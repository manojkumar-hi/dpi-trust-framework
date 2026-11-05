from decimal import Decimal

import pytest

from app.core.capability_catalog import CAPABILITY_CATALOG
from app.core.policies import POLICY_CATALOG
from app.services.agent_adapters.template_adapter import AgentTemplateAdapter
from app.services.agent_templates.finance_agent import prepare_payment, read_budget, review_invoice
from app.services.agent_templates.registry import get_template
from app.services.authorization_engine import AuthorizationEngine


@pytest.mark.asyncio
async def test_finance_tools_return_synthetic_sample_data():
    budget = await read_budget()
    invoice = await review_invoice()
    payment = await prepare_payment(amount=Decimal("1250.00"))

    assert budget["prototype"] is True
    assert budget["budget"]["remaining"] == "101500.00"
    assert invoice["invoice"]["status"] == "PENDING_REVIEW"
    assert payment["payment"]["status"] == "PREPARED_FOR_REVIEW (sample only)"
    assert "no payment was submitted" in payment["notice"]


def test_finance_capabilities_and_policies_are_registered_with_risk_tiers():
    capabilities = {"finance.read_budget", "finance.review_invoice", "finance.prepare_payment"}
    assert capabilities <= set(CAPABILITY_CATALOG)
    rules = {rule.action: rule for rule in POLICY_CATALOG if rule.action in capabilities}
    assert set(rules) == capabilities
    assert all(rule.requires_delegation and rule.required_capability == rule.action for rule in rules.values())
    assert rules["finance.prepare_payment"].required_trust > rules["finance.review_invoice"].required_trust
    assert rules["finance.prepare_payment"].max_recent_risk < rules["finance.review_invoice"].max_recent_risk

    decision = AuthorizationEngine.evaluate({
        "subject": {"identity_status": "active", "trust": {"t": 0.8, "u": 0.3, "rr": 0.2}},
        "action": {"name": "finance.prepare_payment"},
        "resource": {"type": "agent"},
        "delegation": {"is_present": True, "is_valid": True, "capabilities": ["finance.prepare_payment"]},
    })
    assert decision.is_allowed is True

    denied = AuthorizationEngine.evaluate({
        "subject": {"identity_status": "active", "trust": {"t": 0.8, "u": 0.3, "rr": 0.21}},
        "action": {"name": "finance.prepare_payment"},
        "resource": {"type": "agent"},
        "delegation": {"is_present": True, "is_valid": True, "capabilities": ["finance.prepare_payment"]},
    })
    assert denied.is_allowed is False
    assert denied.reason_code == "RECENT_RISK_TOO_HIGH"


def test_finance_template_is_registered():
    template = get_template("finance_agent")
    assert template is not None
    assert set(template.supported_capabilities) == {
        "finance.read_budget",
        "finance.review_invoice",
        "finance.prepare_payment",
    }


@pytest.mark.asyncio
async def test_template_adapter_dispatches_finance_tool():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from uuid import uuid4

    db = MagicMock()
    db.get.return_value = SimpleNamespace(template_id="finance_agent")
    result = await AgentTemplateAdapter().execute_action(uuid4(), "finance.read_budget", {}, db)

    assert result.status == "SUCCESS"
    assert result.data["result"]["budget"]["cost_center"] == "CC-100"
