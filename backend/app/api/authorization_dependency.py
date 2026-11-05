from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import Principal
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.delegation import Delegation
from app.schemas.audit import AuditRecordCreate
from app.services.audit_service import AuditService
from app.services.trust_service import TrustService
from app.services.opa_authorization import evaluate_with_opa
from app.services.delegation_service import verify_delegation
from app.database.connection import SessionLocal


def resolve_policy_target(action_type: str) -> tuple[str, str]:
    if action_type == "agent.read":
        return "system_status", "read"
    if action_type == "credential.issue":
        return "verifiable_credential", "issue"
    if action_type == "delegation.revoke":
        return "delegation", "revoke"
    return "agent", action_type


async def evaluate_authorization(
    resource_type: str,
    action_name: str,
    db: Session,
    principal: Principal,
    agent_id: UUID,
    delegation_id: UUID | None = None,
    event_type: str = "authorization_evaluated",
):
    """Evaluate and audit a request without executing the requested action."""
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.organization_id != principal.organization_id:
        raise HTTPException(status_code=403, detail="Principal not authorized to access this agent")

    agent_identity = db.scalar(select(AgentIdentity).where(AgentIdentity.agent_id == agent_id))
    identity_status = agent_identity.status if agent_identity else "unknown"
    trust_score = TrustService.get_trust_score(db, agent_id)

    delegation_present = delegation_id is not None
    delegation_valid = False
    capabilities: list[str] = []
    if delegation_id:
        delegation = db.get(Delegation, delegation_id)
        if (
            delegation is not None
            and delegation.delegatee_agent_id == agent_id
            and delegation.delegator_organization_id == principal.organization_id
        ):
            try:
                verification = await verify_delegation(db, delegation_id)
                delegation_valid = verification.valid
                if delegation_valid:
                    capabilities = [
                        capability.capability_code
                        for capability in delegation.capabilities
                        if capability.scope.get("permission") != "DENIED"
                    ]
            except Exception:
                delegation_valid = False

    policy_input = {
        "subject": {
            "identity_status": identity_status,
            "trust": {"t": trust_score.trust, "u": trust_score.uncertainty, "rr": trust_score.recent_risk},
        },
        "action": {"name": action_name},
        "resource": {"type": resource_type},
        "delegation": {
            "is_present": delegation_present,
            "is_valid": delegation_valid,
            "capabilities": capabilities,
        },
        "environment": {"time": datetime.now(timezone.utc).isoformat()},
    }
    try:
        decision = await evaluate_with_opa(policy_input)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    audit_db = SessionLocal()
    try:
        AuditService.create_audit_record(audit_db, AuditRecordCreate(
            event_category="AUTHORIZATION",
            event_type=event_type,
            actor_organization_id=principal.organization_id,
            subject_agent_id=agent_id,
            resource_type=resource_type,
            action_requested=action_name,
            authorization_decision="ALLOW" if decision.is_allowed else "DENY",
            reason_code=decision.reason_code,
            policy_id="default_policy",
            trust_snapshot={"t": trust_score.trust, "u": trust_score.uncertainty, "rr": trust_score.recent_risk},
            event_metadata={"delegation_id": str(delegation_id) if delegation_id else None, "capabilities": capabilities},
        ))
        audit_db.commit()
    except Exception:
        audit_db.rollback()
        raise HTTPException(status_code=500, detail="Failed to persist authorization audit record")
    finally:
        audit_db.close()

    return decision

async def authorize_action(
    resource_type: str,
    action_name: str,
    db: Session,
    principal: Principal,
    agent_id: UUID,
    delegation_id: UUID | None = None
):
    decision = await evaluate_authorization(
        resource_type, action_name, db, principal, agent_id, delegation_id
    )

    # 6. Enforcement
    if not decision.is_allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Authorization Denied",
                "reason_code": decision.reason_code,
                "explanation": decision.explanation,
                "evidence": decision.evidence
            }
        )
    return decision
