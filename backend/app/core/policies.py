from dataclasses import dataclass
from typing import Optional

@dataclass
class PolicyRule:
    resource_type: str
    action: str
    action_risk: float
    required_trust: float
    max_recent_risk: float
    max_uncertainty: Optional[float]
    required_capability: Optional[str]
    requires_delegation: bool

# V1 Policy Catalog
POLICY_CATALOG = [
    # Low-risk operation
    PolicyRule(
        resource_type="system_status",
        action="read",
        action_risk=0.1,
        required_trust=0.0,
        max_recent_risk=0.9,
        max_uncertainty=1.0,
        required_capability=None,
        requires_delegation=False
    ),
    # Higher-risk operation
    PolicyRule(
        resource_type="agent_configuration",
        action="update",
        action_risk=0.8,
        required_trust=0.7,
        max_recent_risk=0.3,
        max_uncertainty=0.5,
        required_capability=None,
        requires_delegation=False
    ),
    # Operation requiring specific capability (and delegation)
    PolicyRule(
        resource_type="verifiable_credential",
        action="issue",
        action_risk=0.9,
        required_trust=0.8,
        max_recent_risk=0.1,
        max_uncertainty=0.2,
        required_capability="credential.issue",
        requires_delegation=True
    ),
    # Operation requiring delegation
    PolicyRule(
        resource_type="delegation",
        action="revoke",
        action_risk=0.5,
        required_trust=0.5,
        max_recent_risk=0.5,
        max_uncertainty=0.8,
        required_capability=None,
        requires_delegation=True
    ),
    # LangChain tool execution
    PolicyRule(
        resource_type="agent",
        action="langchain.tool.add",
        action_risk=0.1,
        required_trust=0.0,
        max_recent_risk=0.9,
        max_uncertainty=1.0,
        required_capability=None,
        requires_delegation=False
    ),
    # HR template operations require an active delegation carrying the exact
    # capability. State-changing sample requests also require the baseline trust score.
    *[
        PolicyRule(
            resource_type="agent",
            action=capability,
            action_risk=0.3 if capability == "hr.submit_leave_request" else 0.1,
            required_trust=0.5 if capability == "hr.submit_leave_request" else 0.0,
            max_recent_risk=0.9,
            max_uncertainty=1.0,
            required_capability=capability,
            requires_delegation=True,
        )
        for capability in (
            "hr.read_policies",
            "hr.calculate_leave_balance",
            "hr.view_holiday_calendar",
            "hr.check_leave_status",
            "hr.submit_leave_request",
            "hr.view_employee_profile",
            "hr.plan_training_program",
        )
    ],
    # Finance template operations require an active delegation carrying the exact
    # capability. Payment preparation is intentionally the strictest sample action.
    *[
        PolicyRule(
            resource_type="agent",
            action=capability,
            action_risk={
                "finance.read_budget": 0.1,
                "finance.review_invoice": 0.4,
                "finance.prepare_payment": 0.8,
            }[capability],
            required_trust={
                "finance.read_budget": 0.0,
                "finance.review_invoice": 0.5,
                "finance.prepare_payment": 0.8,
            }[capability],
            max_recent_risk={
                "finance.read_budget": 0.9,
                "finance.review_invoice": 0.4,
                "finance.prepare_payment": 0.2,
            }[capability],
            max_uncertainty={
                "finance.read_budget": 1.0,
                "finance.review_invoice": 0.6,
                "finance.prepare_payment": 0.3,
            }[capability],
            required_capability=capability,
            requires_delegation=True,
        )
        for capability in (
            "finance.read_budget",
            "finance.review_invoice",
            "finance.prepare_payment",
        )
    ],
]
