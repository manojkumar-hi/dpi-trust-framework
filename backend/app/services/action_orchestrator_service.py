import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
import json
import hashlib

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.agent_action_log import AgentActionLog
from app.models.agent import Agent
from app.models.agent_identity import AgentIdentity
from app.models.verifiable_credential import VerifiableCredential
from app.models.agent_trust_state import AgentTrustState
from app.services.vp_auth_service import verify_vp_and_consume_challenge
from app.services.trust_service import TrustService
from app.services.idempotency_service import IdempotencyService
from app.services.audit_service import AuditService
from app.schemas.audit import AuditRecordCreate
from app.schemas.trust import EvidenceIngestionRequest
from app.core.policies import POLICY_CATALOG
from app.services.vc_verification_service import verify_vc_jwt

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
        source_agent_did: str | None = None,
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

        declared_source_agent_did = source_agent_did
        source_agent_did = agent_identity.did
        agent_id = agent_identity.agent_id
        principal_org_id = agent_identity.agent.organization_id

        if declared_source_agent_did is not None and declared_source_agent_did != agent_identity.did:
            raise HTTPException(status_code=401, detail="Source agent DID does not match the authenticated credential")

        # Target resolution for Action Log foreign key
        target_agent = db.scalar(select(Agent).join(Agent.identity).where(Agent.identity.has(did=target_agent_did)))
        if not target_agent:
            raise HTTPException(status_code=404, detail="Target agent not found")
        if target_agent.organization_id != principal_org_id:
            raise HTTPException(status_code=403, detail="Target agent belongs to a different organization")
        target_identity = db.scalar(select(AgentIdentity).where(AgentIdentity.agent_id == target_agent.id))
        if not target_identity or target_identity.status != "active":
            raise HTTPException(status_code=403, detail="Target agent identity is not active")
        target_credential = db.scalar(
            select(VerifiableCredential)
            .where(VerifiableCredential.subject_agent_id == target_agent.id)
            .where(VerifiableCredential.status == "active")
            .where(VerifiableCredential.vc_jwt.is_not(None))
            .order_by(VerifiableCredential.created_at.desc())
        )
        if not target_credential:
            raise HTTPException(status_code=403, detail="Target agent has no active Verifiable Credential")
        target_vc = verify_vc_jwt(target_credential.vc_jwt, db)
        if not target_vc.valid or target_vc.subject_did != target_identity.did:
            raise HTTPException(status_code=403, detail="Target agent Verifiable Credential is invalid")

        # Audit: Action Requested
        _audit_action(db, "action_requested", principal_org_id, agent_id, "PENDING", "VALIDATING", {
            "action_type": action_type, "target_agent": target_agent_did, "execution_id": execution_id
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
            payload_hash=hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest(),
            timestamp=now
        )
        db.add(action_log)
        db.flush()

        try:
            # 2. Extract Trust Score
            trust_response = TrustService.get_trust_score(db, target_agent.id)

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
                        if delegation and delegation.delegatee_agent_id == target_agent.id and delegation.delegator_organization_id == principal_org_id:
                            capabilities = [
                                c.capability_code for c in delegation.capabilities
                                if c.scope.get("permission") != "DENIED"
                            ]
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
                    "identity_status": target_identity.status,
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

            from app.services.opa_authorization import evaluate_with_opa
            try:
                decision = await evaluate_with_opa(input_data)
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

            if not decision.is_allowed:
                _audit_action(db, "action_denied", principal_org_id, agent_id, "DENY", decision.reason_code, {
                    "action_type": action_type,
                    "trust_score": trust_response.trust,
                    "explanation": decision.explanation,
                    "execution_id": execution_id,
                })
                raise HTTPException(status_code=403, detail={"error": "Authorization Denied", "reason": decision.reason_code, "explanation": decision.explanation})

            # 4. REAL Operation Dispatch via AgentRuntimeRegistry
            if action_type == "hr.plan_training_program":
                from app.services.agent_workflow_service import execute_training_program_workflow

                result = await execute_training_program_workflow(
                    db,
                    organization_id=principal_org_id,
                    source_agent=agent_identity.agent,
                    parent_execution_id=execution_id,
                    payload=payload,
                )
                execution_result = type("WorkflowResult", (), {"status": "SUCCESS", "data": result, "error": None})()
            else:
                from app.services.agent_adapters import registry
                adapter = await registry.get_adapter_for(action_type, payload)
                if not adapter:
                    _audit_action(db, "action_denied", principal_org_id, agent_id, "DENY", "UNSUPPORTED_ACTION", {
                        "action_type": action_type, "execution_id": execution_id
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
                    "action_type": action_type, "error": execution_result.error, "execution_id": execution_id
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
            evidence = TrustService.ingest_evidence(db, target_agent.id, evidence_req, principal_org_id)
            evidence.action_log_id = action_log.id
            
            _audit_action(db, "action_executed", principal_org_id, agent_id, "ALLOW", "SUCCESS", {
                "action_type": action_type, "target_agent": target_agent_did, "execution_id": execution_id
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
            action_log.status = "FAILED" if e.status_code >= 500 else "DENIED"
            if idempotency_key and e.status_code < 500:
                IdempotencyService.update_idempotency_response(
                    db, principal_org_id, idempotency_key, {"detail": e.detail}, e.status_code
                )
            db.commit()
            raise e
        except Exception as e:
            action_log.status = "FAILED"
            _audit_action(db, "action_failed", principal_org_id, agent_id, "ERROR", "INTERNAL_ERROR", {
                "action_type": action_type, "error": str(e), "execution_id": execution_id
            })
            if idempotency_key:
                IdempotencyService.update_idempotency_response(
                    db, principal_org_id, idempotency_key, {"detail": "Internal server error"}, 500
                )
            db.commit()
            logger.error(f"Action execution failed: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
