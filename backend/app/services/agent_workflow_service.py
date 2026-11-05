"""Server-mediated workflows that coordinate more than one local agent."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.delegation import Delegation
from app.models.verifiable_credential import VerifiableCredential
from app.schemas.audit import AuditRecordCreate
from app.schemas.trust import EvidenceIngestionRequest
from app.services.agent_adapters import registry
from app.services.audit_service import AuditService
from app.services.delegation_service import verify_delegation
from app.services.trust_service import TrustService
from app.services.vc_verification_service import verify_vc_jwt


def _audit_workflow_event(
    db: Session,
    event_type: str,
    organization_id: UUID,
    subject_agent_id: UUID,
    decision: str,
    reason: str,
    metadata: dict[str, Any],
) -> None:
    AuditService.create_audit_record(
        db,
        AuditRecordCreate(
            event_category="AGENT_ACTION",
            event_type=event_type,
            actor_organization_id=organization_id,
            subject_agent_id=subject_agent_id,
            resource_type="agent_action",
            action_requested=metadata.get("action_type"),
            authorization_decision=decision,
            reason_code=reason,
            event_metadata=metadata,
        ),
    )


async def execute_training_program_workflow(
    db: Session,
    *,
    organization_id: UUID,
    source_agent: Agent,
    parent_execution_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Have HR obtain a Finance budget and combine it into a training plan."""
    finance_agent = db.scalar(
        select(Agent)
        .where(Agent.organization_id == organization_id)
        .where(Agent.template_id == "finance_agent")
        .where(Agent.status == "active")
        .order_by(Agent.created_at)
    )
    if finance_agent is None:
        raise HTTPException(status_code=403, detail="No active Finance Agent is available for this workflow")

    finance_identity = db.scalar(
        select(AgentIdentity).where(AgentIdentity.agent_id == finance_agent.id)
    )
    if finance_identity is None or finance_identity.status != "active":
        raise HTTPException(status_code=403, detail="Finance Agent identity is not active")

    finance_credential = db.scalar(
        select(VerifiableCredential)
        .where(VerifiableCredential.subject_agent_id == finance_agent.id)
        .where(VerifiableCredential.issuer_organization_id == organization_id)
        .where(VerifiableCredential.status == "active")
        .where(VerifiableCredential.vc_jwt.is_not(None))
        .order_by(VerifiableCredential.created_at.desc())
    )
    if finance_credential is None:
        raise HTTPException(status_code=403, detail="Finance Agent has no active Verifiable Credential")
    finance_vc = verify_vc_jwt(finance_credential.vc_jwt, db)
    if not finance_vc.valid or finance_vc.subject_did != finance_identity.did:
        raise HTTPException(status_code=403, detail="Finance Agent Verifiable Credential is invalid")

    finance_delegation = None
    for delegation in db.scalars(
        select(Delegation)
        .where(Delegation.delegator_organization_id == organization_id)
        .where(Delegation.delegatee_agent_id == finance_agent.id)
        .where(Delegation.status == "active")
    ).all():
        if any(
            capability.capability_code == "finance.read_budget"
            and capability.scope.get("permission") != "DENIED"
            for capability in delegation.capabilities
        ):
            finance_delegation = delegation
            break
    if finance_delegation is None:
        raise HTTPException(status_code=403, detail="Finance Agent is not delegated finance.read_budget")

    delegation_result = await verify_delegation(db, finance_delegation.id)
    if not delegation_result.valid:
        raise HTTPException(status_code=403, detail="Finance Agent delegation could not be verified")

    trust = TrustService.get_trust_score(db, finance_agent.id)
    from app.services.opa_authorization import evaluate_with_opa

    decision = await evaluate_with_opa(
        {
            "subject": {
                "identity_status": finance_identity.status,
                "trust": {"t": trust.trust, "u": trust.uncertainty, "rr": trust.recent_risk},
            },
            "action": {"name": "finance.read_budget"},
            "resource": {"type": "agent"},
            "delegation": {
                "is_present": True,
                "is_valid": True,
                "capabilities": ["finance.read_budget"],
            },
        }
    )
    metadata = {
        "action_type": "finance.read_budget",
        "workflow": "workforce_training_program",
        "workflow_step": "finance_budget_lookup",
        "parent_execution_id": parent_execution_id,
        "source_agent_did": source_agent.identity.did,
        "target_agent_did": finance_identity.did,
    }
    if not decision.is_allowed:
        _audit_workflow_event(db, "agent_to_agent_denied", organization_id, finance_agent.id, "DENY", decision.reason_code, metadata)
        raise HTTPException(status_code=403, detail={"error": "Internal Finance request denied", "reason": decision.reason_code, "explanation": decision.explanation})

    _audit_workflow_event(db, "agent_to_agent_authorized", organization_id, finance_agent.id, "ALLOW", "AUTHORIZED", metadata)
    adapter = await registry.get_adapter_for("finance.read_budget", {"cost_center": payload.get("cost_center", "CC-100")})
    if adapter is None:
        raise HTTPException(status_code=500, detail="Finance budget tool is unavailable")
    finance_result = await adapter.execute_action(
        target_agent_id=finance_agent.id,
        action_type="finance.read_budget",
        payload={"cost_center": payload.get("cost_center", "CC-100")},
        db=db,
    )
    if finance_result.status != "SUCCESS":
        raise HTTPException(status_code=500, detail=finance_result.error or "Finance budget lookup failed")

    _audit_workflow_event(db, "agent_to_agent_completed", organization_id, finance_agent.id, "ALLOW", "SUCCESS", metadata)
    TrustService.ingest_evidence(
        db,
        finance_agent.id,
        EvidenceIngestionRequest(
            outcome="success",
            severity=None,
            evidence_quality=1.0,
            informative_value=1.0,
            action_metadata={"action_type": "finance.read_budget", "workflow": "workforce_training_program"},
        ),
        organization_id,
    )

    budget_result = finance_result.data.get("result", {})
    from app.services.agent_templates.hr_agent import plan_training_program

    plan = await plan_training_program(
        department=payload.get("department", "Customer Support"),
        training_topic=payload.get("training_topic", "Service quality and compliance"),
        budget=budget_result.get("budget", {}),
    )
    plan["supporting_agent"] = finance_agent.name
    plan["workflow_parent_execution_id"] = parent_execution_id
    return plan
