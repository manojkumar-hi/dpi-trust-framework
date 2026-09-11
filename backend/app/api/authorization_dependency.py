from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import Principal
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.delegation import Delegation
from app.services.trust_service import TrustService
from app.services.authorization_engine import AuthorizationEngine
from app.services.delegation_service import verify_delegation

async def authorize_action(
    resource_type: str,
    action_name: str,
    db: Session,
    principal: Principal,
    agent_id: UUID,
    delegation_id: UUID | None = None
):
    # 1. Fetch Agent & Identity
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    if agent.organization_id != principal.organization_id:
        raise HTTPException(status_code=403, detail="Principal not authorized to access this agent")

    agent_identity = db.scalar(select(AgentIdentity).where(AgentIdentity.agent_id == agent_id))
    identity_status = agent_identity.status if agent_identity else "unknown"

    # 2. Fetch Trust Score
    trust_score = TrustService.get_trust_score(db, agent_id)
    
    # 3. Verify Delegation
    del_present = False
    del_valid = False
    capabilities = []
    
    if delegation_id:
        del_present = True
        try:
            del_result = await verify_delegation(db, delegation_id)
            del_valid = del_result.valid
            if del_valid:
                delegation = db.get(Delegation, delegation_id)
                if delegation:
                    capabilities = [c.capability_code for c in delegation.capabilities]
        except Exception:
            del_valid = False

    # 4. Assemble Context
    input_data = {
        "subject": {
            "identity_status": identity_status,
            "trust": {
                "t": trust_score.trust,
                "u": trust_score.uncertainty,
                "rr": trust_score.recent_risk
            }
        },
        "action": {
            "name": action_name,
            "risk_level": 0.0  # Contextual info only
        },
        "resource": {
            "type": resource_type
        },
        "delegation": {
            "is_present": del_present,
            "is_valid": del_valid,
            "capabilities": capabilities
        },
        "environment": {
            "time": datetime.now(timezone.utc).isoformat()
        }
    }

    # 5. Pure Engine Evaluation
    decision = AuthorizationEngine.evaluate(input_data)
    
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
