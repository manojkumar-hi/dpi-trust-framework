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
    }
)


def get_capability_definition(code: str) -> CapabilityDefinition | None:
    return CAPABILITY_CATALOG.get(code)