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
    )
]
