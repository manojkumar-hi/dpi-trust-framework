import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.agent_action_log import AgentActionLog
from app.models.agent import Agent
from app.models.agent_trust_state import AgentTrustState
from app.services.vp_auth_service import verify_vp_and_consume_challenge
from app.services.trust_service import TrustService
from app.services.idempotency_service import IdempotencyService
from app.services.audit_service import AuditService
from app.schemas.audit import AuditRecordCreate
from app.schemas.trust import EvidenceIngestionRequest
from app.core.policies import POLICY_CATALOG

logger = logging.getLogger(__name__)

def _audit_action(db: Session, event_type: str, actor_org: UUID, subject_agent: UUID, decision: str, reason: str, metadata: dict):
    record = AuditRecordCreate(
        event_category="AGENT_ACTION",
        event_type=event_type,
        actor_organization_id=actor_org,
        subject_agent_id=subject_agent,
        resource_type="agent_action",
        action_requested=metadata.get("action_type"),
        authorization_decision=decision,
        reason_code=reason,
        event_metadata=metadata
    )
    AuditService.create_audit_record(db, record)

class ActionOrchestratorService:
    @classmethod
    async def execute_action(
        cls,
        db: Session,
        challenge_id: UUID,
        vp_jwt: str,
        target_agent_did: str,
        action_type: str,
        resource_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        delegation_id: UUID | None = None,
        endpoint_path: str = "/api/v1/gateway/action"
    ) -> dict[str, Any]:
        """
        Execute an action triggered by an agent, validating auth, trust, and generating evidence.
        """
        execution_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # 1. VP Authentication
        try:
            agent_identity = verify_vp_and_consume_challenge(db, challenge_id, vp_jwt)
        except Exception as e:
            # Audit handled by vp_auth_service
            logger.error(f"VP Authentication failed: {e}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

        source_agent_did = agent_identity.did
        agent_id = agent_identity.agent_id
        principal_org_id = agent_identity.agent.organization_id

        # Target resolution for Action Log foreign key
        target_agent = db.scalar(select(Agent).join(Agent.identity).where(Agent.identity.has(did=target_agent_did)))
        if not target_agent:
            raise HTTPException(status_code=404, detail="Target agent not found")

        # Audit: Action Requested
        _audit_action(db, "action_requested", principal_org_id, agent_id, "PENDING", "VALIDATING", {
            "action_type": action_type, "target_agent": target_agent_did
        })

        # Idempotency Check
        if idempotency_key:
            cached_response = IdempotencyService.check_and_lock_idempotency(
                db, principal_org_id, idempotency_key, endpoint_path, payload
            )
            if cached_response is not None:
                # Return the cached response successfully without executing anything
                return cached_response

        # Action Log initialization
        action_log = AgentActionLog(
            execution_id=execution_id,
            source_agent_did=source_agent_did,
            target_agent_did=target_agent_did,
            source_agent_id=agent_id,
            target_agent_id=target_agent.id,
            action_type=action_type,
            resource_id=resource_id,
            status="PENDING",
            timestamp=now
        )
        db.add(action_log)
        db.flush()

        try:
            # 2. Extract Trust Score
            trust_response = TrustService.get_trust_score(db, agent_id)

            del_present = False
            del_valid = False
            capabilities = []
            
            if delegation_id:
                del_present = True
                from app.services.delegation_service import verify_delegation
                from app.models.delegation import Delegation
                try:
                    del_result = await verify_delegation(db, delegation_id)
                    del_valid = del_result.valid
                    if del_valid:
                        delegation = db.get(Delegation, delegation_id)
                        if delegation:
                            capabilities = [c.capability_code for c in delegation.capabilities]
                except Exception:
                    del_valid = False

            # 3. Authorization Engine Evaluation
            if action_type == "agent.read":
                eval_resource_type = "system_status"
                eval_action_name = "read"
            elif action_type == "verifiable_credential.issue":
                eval_resource_type = "verifiable_credential"
                eval_action_name = "issue"
            elif action_type == "delegation.revoke":
                eval_resource_type = "delegation"
                eval_action_name = "revoke"
            else:
                eval_resource_type = "agent"
                eval_action_name = action_type

            input_data = {
                "subject": {
                    "identity_status": agent_identity.status,
                    "trust": {
                        "t": trust_response.trust,
                        "u": trust_response.uncertainty,
                        "rr": trust_response.recent_risk
                    }
                },
                "action": {
                    "name": eval_action_name
                },
                "resource": {
                    "type": eval_resource_type
                },
                "delegation": {
                    "is_present": del_present,
                    "is_valid": del_valid,
                    "capabilities": capabilities
                }
            }

            from app.services.authorization_engine import AuthorizationEngine
            decision = AuthorizationEngine.evaluate(input_data)

            if not decision.is_allowed:
                _audit_action(db, "action_denied", principal_org_id, agent_id, "DENY", decision.reason_code, {
                    "action_type": action_type,
                    "trust_score": trust_response.trust,
                    "explanation": decision.explanation
                })
                raise HTTPException(status_code=403, detail={"error": "Authorization Denied", "reason": decision.reason_code, "explanation": decision.explanation})

            # 4. REAL Operation Dispatch via AgentRuntimeRegistry
            from app.services.agent_adapters import registry
            adapter = await registry.get_adapter_for(action_type, payload)
            if not adapter:
                _audit_action(db, "action_denied", principal_org_id, agent_id, "DENY", "UNSUPPORTED_ACTION", {
                    "action_type": action_type
                })
                raise HTTPException(status_code=400, detail="Unsupported action type")
                
            execution_result = await adapter.execute_action(
                target_agent_id=target_agent.id,
                action_type=action_type,
                payload=payload,
                db=db
            )
            
            if execution_result.status != "SUCCESS":
                # Adapter failed
                action_log.status = "FAILED"
                _audit_action(db, "action_failed", principal_org_id, agent_id, "ERROR", "EXECUTION_FAILED", {
                    "action_type": action_type, "error": execution_result.error
                })
                raise HTTPException(status_code=500, detail=execution_result.error or "Action execution failed")
                
            result = execution_result.data

            # 5. Success - generate positive evidence
            action_log.status = "SUCCESS"
            
            evidence_req = EvidenceIngestionRequest(
                outcome="success",
                severity=None,
                evidence_quality=1.0,
                informative_value=1.0,
                action_metadata={"action_type": action_type, "target": target_agent_did}
            )
            evidence = TrustService.ingest_evidence(db, agent_id, evidence_req, principal_org_id)
            evidence.action_log_id = action_log.id
            
            _audit_action(db, "action_executed", principal_org_id, agent_id, "ALLOW", "SUCCESS", {
                "action_type": action_type, "target_agent": target_agent_did
            })

            final_response = {
                "execution_id": execution_id,
                "status": "SUCCESS",
                "result": result
            }

            if idempotency_key:
                IdempotencyService.update_idempotency_response(
                    db, principal_org_id, idempotency_key, final_response, 200
                )

            db.commit()
            return final_response

        except HTTPException as e:
            action_log.status = "DENIED"
            if idempotency_key and e.status_code < 500:
                IdempotencyService.update_idempotency_response(
                    db, principal_org_id, idempotency_key, {"detail": e.detail}, e.status_code
                )
            db.commit()
            raise e
        except Exception as e:
            action_log.status = "FAILED"
            _audit_action(db, "action_failed", principal_org_id, agent_id, "ERROR", "INTERNAL_ERROR", {
                "action_type": action_type, "error": str(e)
            })
            if idempotency_key:
                IdempotencyService.update_idempotency_response(
                    db, principal_org_id, idempotency_key, {"detail": "Internal server error"}, 500
                )
            db.commit()
            logger.error(f"Action execution failed: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
