from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


CAPABILITY_CATALOG_VERSION = "1.0"


@dataclass(frozen=True)
class CapabilityDefinition:
    code: str
    resource_type: str
    description: str


CAPABILITY_CATALOG: Mapping[str, CapabilityDefinition] = MappingProxyType(
    {
        "credential.issue": CapabilityDefinition(
            code="credential.issue",
            resource_type="verifiable_credential",
            description="Issue verifiable credentials",
        ),
        "credential.read": CapabilityDefinition(
            code="credential.read",
            resource_type="verifiable_credential",
            description="Read verifiable credentials",
        ),
        "credential.verify": CapabilityDefinition(
            code="credential.verify",
            resource_type="verifiable_credential",
            description="Verify verifiable credentials",
        ),
        "credential.revoke": CapabilityDefinition(
            code="credential.revoke",
            resource_type="verifiable_credential",
            description="Revoke verifiable credentials",
        ),
        "agent.read": CapabilityDefinition(
            code="agent.read",
            resource_type="agent",
            description="Read agent metadata",
        ),
        "agent.manage": CapabilityDefinition(
            code="agent.manage",
            resource_type="agent",
            description="Manage agent lifecycle",
        ),
        "hr.read_policies": CapabilityDefinition(
            code="hr.read_policies",
            resource_type="hr_policy",
            description="Read HR policies",
        ),
        "hr.calculate_leave_balance": CapabilityDefinition(
            code="hr.calculate_leave_balance",
            resource_type="hr_leave",
            description="Calculate employee leave balance",
        ),
        "hr.view_holiday_calendar": CapabilityDefinition(
            code="hr.view_holiday_calendar",
            resource_type="hr_calendar",
            description="View the HR holiday calendar",
        ),
        "hr.check_leave_status": CapabilityDefinition(
            code="hr.check_leave_status",
            resource_type="hr_leave",
            description="Check the status of a leave request",
        ),
        "hr.submit_leave_request": CapabilityDefinition(
            code="hr.submit_leave_request",
            resource_type="hr_leave",
            description="Submit a leave request",
        ),
        "hr.view_employee_profile": CapabilityDefinition(
            code="hr.view_employee_profile",
            resource_type="hr_employee",
            description="View an employee profile",
        ),
        "hr.plan_training_program": CapabilityDefinition(
            code="hr.plan_training_program",
            resource_type="hr_training",
            description="Plan a workforce training program with a budget check",
        ),
        "finance.read_budget": CapabilityDefinition(
            code="finance.read_budget",
            resource_type="finance_budget",
            description="Read a finance budget summary",
        ),
        "finance.review_invoice": CapabilityDefinition(
            code="finance.review_invoice",
            resource_type="finance_invoice",
            description="Review an invoice for sample policy and variance signals",
        ),
        "finance.prepare_payment": CapabilityDefinition(
            code="finance.prepare_payment",
            resource_type="finance_payment",
            description="Prepare a payment instruction without submitting it",
        ),
    }
)


def get_capability_definition(code: str) -> CapabilityDefinition | None:
    return CAPABILITY_CATALOG.get(code)
