package dpi.authz

import future.keywords.if

default decision := {
    "is_allowed": false,
    "reason_code": "NO_MATCHING_POLICY",
    "explanation": "No policy matches the requested resource and action",
    "evidence": {}
}

rules := {
    "system_status": {
        "read": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "", "requires_delegation": false},
    },
    "agent_configuration": {
        "update": {"required_trust": 0.7, "max_recent_risk": 0.3, "max_uncertainty": 0.5, "required_capability": "", "requires_delegation": false},
    },
    "verifiable_credential": {
        "issue": {"required_trust": 0.8, "max_recent_risk": 0.1, "max_uncertainty": 0.2, "required_capability": "credential.issue", "requires_delegation": true},
    },
    "delegation": {
        "revoke": {"required_trust": 0.5, "max_recent_risk": 0.5, "max_uncertainty": 0.8, "required_capability": "", "requires_delegation": true},
    },
    "agent": {
        "langchain.tool.add": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "", "requires_delegation": false},
        "hr.read_policies": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.read_policies", "requires_delegation": true},
        "hr.calculate_leave_balance": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.calculate_leave_balance", "requires_delegation": true},
        "hr.view_holiday_calendar": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.view_holiday_calendar", "requires_delegation": true},
        "hr.check_leave_status": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.check_leave_status", "requires_delegation": true},
        "hr.submit_leave_request": {"required_trust": 0.5, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.submit_leave_request", "requires_delegation": true},
        "hr.view_employee_profile": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.view_employee_profile", "requires_delegation": true},
        "hr.plan_training_program": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "hr.plan_training_program", "requires_delegation": true},
        "finance.read_budget": {"required_trust": 0.0, "max_recent_risk": 0.9, "max_uncertainty": 1.0, "required_capability": "finance.read_budget", "requires_delegation": true},
        "finance.review_invoice": {"required_trust": 0.5, "max_recent_risk": 0.4, "max_uncertainty": 0.6, "required_capability": "finance.review_invoice", "requires_delegation": true},
        "finance.prepare_payment": {"required_trust": 0.8, "max_recent_risk": 0.2, "max_uncertainty": 0.3, "required_capability": "finance.prepare_payment", "requires_delegation": true},
    },
}

policy := rules[input.resource.type][input.action.name]

capability_present if {
    some index
    input.delegation.capabilities[index] == policy.required_capability
}

delegation_ok if {
    not policy.requires_delegation
}

delegation_ok if {
    policy.requires_delegation
    input.delegation.is_present
    input.delegation.is_valid
}

capability_ok if {
    policy.required_capability == ""
}

capability_ok if {
    policy.required_capability != ""
    capability_present
}

evidence := {
    "matched_policy": {"resource_type": input.resource.type, "action": input.action.name},
    "required_trust": policy.required_trust,
    "actual_trust": input.subject.trust.t,
    "maximum_allowed_recent_risk": policy.max_recent_risk,
    "actual_recent_risk": input.subject.trust.rr,
    "maximum_allowed_uncertainty": policy.max_uncertainty,
    "actual_uncertainty": input.subject.trust.u,
    "required_capability": policy.required_capability,
    "delegation_validity": input.delegation.is_valid,
} if {
    policy
}

decision := {
    "is_allowed": false,
    "reason_code": "IDENTITY_INVALID",
    "explanation": "Identity is not active",
    "evidence": evidence,
} if {
    policy
    input.subject.identity_status != "active"
} else := {
    "is_allowed": false,
    "reason_code": "DELEGATION_INVALID",
    "explanation": "Required delegation is missing",
    "evidence": evidence,
} if {
    policy
    policy.requires_delegation
    not input.delegation.is_present
} else := {
    "is_allowed": false,
    "reason_code": "DELEGATION_INVALID",
    "explanation": "Delegation is present but invalid",
    "evidence": evidence,
} if {
    policy
    policy.requires_delegation
    input.delegation.is_present
    not input.delegation.is_valid
} else := {
    "is_allowed": false,
    "reason_code": "CAPABILITY_DENIED",
    "explanation": "Required capability missing from delegation",
    "evidence": evidence,
} if {
    policy
    policy.required_capability != ""
    not capability_present
} else := {
    "is_allowed": false,
    "reason_code": "RECENT_RISK_TOO_HIGH",
    "explanation": sprintf("Recent risk %v exceeds max %v", [input.subject.trust.rr, policy.max_recent_risk]),
    "evidence": evidence,
} if {
    policy
    input.subject.trust.rr > policy.max_recent_risk
} else := {
    "is_allowed": false,
    "reason_code": "UNCERTAINTY_TOO_HIGH",
    "explanation": sprintf("Uncertainty %v exceeds max %v", [input.subject.trust.u, policy.max_uncertainty]),
    "evidence": evidence,
} if {
    policy
    input.subject.trust.u > policy.max_uncertainty
} else := {
    "is_allowed": false,
    "reason_code": "TRUST_BELOW_THRESHOLD",
    "explanation": sprintf("Trust %v below required %v", [input.subject.trust.t, policy.required_trust]),
    "evidence": evidence,
} if {
    policy
    input.subject.trust.t < policy.required_trust
} else := {
    "is_allowed": true,
    "reason_code": "AUTHORIZED",
    "explanation": "Request authorized according to policy",
    "evidence": evidence,
} if {
    policy
}
