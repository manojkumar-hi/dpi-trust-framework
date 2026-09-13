import math
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_trust_state import AgentTrustState
from app.models.behavioral_evidence import BehavioralEvidence
from app.schemas.trust import EvidenceIngestionRequest, TrustScoreResponse
from app.schemas.audit import AuditRecordCreate
from app.services.audit_service import AuditService


class TrustService:
    R_MAX_PER_WINDOW = 10.0
    HALF_LIFE_DAYS = 30.0

    @classmethod
    def ingest_evidence(
        cls,
        db: Session,
        agent_id: UUID,
        request: EvidenceIngestionRequest,
        principal_org_id: UUID,
    ) -> BehavioralEvidence:
        
        # 1. Verify Agent & Principal Ownership
        agent_stmt = select(Agent).where(Agent.id == agent_id)
        agent = db.scalar(agent_stmt)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        if agent.organization_id != principal_org_id:
            raise HTTPException(status_code=403, detail="Principal not authorized to ingest evidence for this agent")

        now = datetime.now(timezone.utc)
        
        # 2. Retrieve or Create Trust State
        state_stmt = select(AgentTrustState).where(AgentTrustState.agent_id == agent_id).with_for_update()
        trust_state = db.scalar(state_stmt)

        if trust_state:
            # Prevent out-of-order timestamps
            last_updated_at = trust_state.last_updated_at
            if last_updated_at.tzinfo is None:
                last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)
            if now < last_updated_at:
                raise HTTPException(status_code=400, detail="Out-of-order evidence timestamp rejected")
        else:
            # Create fresh state
            trust_state = AgentTrustState(
                agent_id=agent_id,
                positive_evidence_r=0.0,
                negative_evidence_s=0.0,
                current_window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
                current_window_r=0.0,
                last_updated_at=now
            )
            db.add(trust_state)

        # 3. Apply Temporal Decay to Existing State
        last_updated_at = trust_state.last_updated_at
        if last_updated_at.tzinfo is None:
            last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)
        elapsed_days = (now - last_updated_at).total_seconds() / 86400.0
        decay = 2.0 ** (-elapsed_days / cls.HALF_LIFE_DAYS)
        
        # Clamp decay to exactly 1.0 if elapsed time is zero, prevent > 1.0 just in case
        decay = min(max(decay, 0.0), 1.0)

        trust_state.positive_evidence_r *= decay
        trust_state.negative_evidence_s *= decay

        # 4. Handle Window Rollover
        current_window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        state_window_start = trust_state.current_window_start
        if state_window_start.tzinfo is None:
            state_window_start = state_window_start.replace(tzinfo=timezone.utc)
        if current_window_start > state_window_start:
            trust_state.current_window_start = current_window_start
            trust_state.current_window_r = 0.0

        # 5. Process New Evidence
        if request.outcome == "success":
            raw_positive = request.informative_value * request.evidence_quality
            remaining_cap = cls.R_MAX_PER_WINDOW - trust_state.current_window_r
            accepted_positive = min(raw_positive, max(remaining_cap, 0.0))
            
            trust_state.current_window_r += accepted_positive
            trust_state.positive_evidence_r += accepted_positive
        else:
            # Failure
            negative = request.severity * request.evidence_quality
            trust_state.negative_evidence_s += negative

        trust_state.last_updated_at = now

        # 6. Insert Evidence Record
        evidence = BehavioralEvidence(
            agent_id=agent_id,
            timestamp=now,
            outcome=request.outcome,
            severity=request.severity,
            evidence_quality=request.evidence_quality,
            informative_value=request.informative_value,
            action_metadata=request.action_metadata,
            created_at=now
        )
        db.add(evidence)
        
        # 7. Audit Logging
        # Subjective Logic math: r, s, b, d, u, t
        r_current = trust_state.positive_evidence_r
        s_current = trust_state.negative_evidence_s
        denom = r_current + s_current + 2.0
        u_val = 2.0 / denom
        t_val = (r_current / denom) + 0.5 * u_val
        
        audit_record = AuditRecordCreate(
            event_category="TRUST",
            event_type="evidence_ingested",
            actor_organization_id=principal_org_id,
            subject_agent_id=agent_id,
            resource_type="trust_evidence",
            action_requested="ingest_evidence",
            trust_snapshot={
                "t": t_val,
                "u": u_val,
                "rr": None  # Optional to recalculate here, it relies on complex querying. We'll leave it out or provide dummy.
            },
            event_metadata={
                "outcome": request.outcome,
                "severity": request.severity,
                "evidence_quality": request.evidence_quality,
                "informative_value": request.informative_value
            }
        )
        AuditService.create_audit_record(db, audit_record)

        # Triggers DB transaction commit
        db.commit()
        db.refresh(evidence)

        return evidence

    @classmethod
    def get_trust_score(cls, db: Session, agent_id: UUID) -> TrustScoreResponse:
        # Check Agent existence
        agent_stmt = select(Agent).where(Agent.id == agent_id)
        agent = db.scalar(agent_stmt)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        now = datetime.now(timezone.utc)

        # 1. Calculate Recent Security Risk EXACTLY from negative records
        evidence_stmt = select(BehavioralEvidence).where(
            BehavioralEvidence.agent_id == agent_id,
            BehavioralEvidence.outcome == "failure"
        )
        negative_events = db.scalars(evidence_stmt).all()

        rr_product = 1.0
        for ev in negative_events:
            ev_time = ev.timestamp
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
            # Ensure age_days >= 0
            age_days = max(0.0, (now - ev_time).total_seconds() / 86400.0)
            d = 2.0 ** (-age_days / cls.HALF_LIFE_DAYS)
            p = (ev.severity / 16.0) * ev.evidence_quality * d
            # Clamp p to [0,1] for safety
            p = min(max(p, 0.0), 1.0)
            rr_product *= (1.0 - p)

        rr = 1.0 - rr_product
        # Clamp tiny floating point errors
        rr = min(max(rr, 0.0), 1.0)

        # 2. Calculate Base Trust Score (Subjective Logic)
        state_stmt = select(AgentTrustState).where(AgentTrustState.agent_id == agent_id)
        trust_state = db.scalar(state_stmt)

        r = 0.0
        s = 0.0
        
        if trust_state:
            last_updated_at = trust_state.last_updated_at
            if last_updated_at.tzinfo is None:
                last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)
            elapsed_days = max(0.0, (now - last_updated_at).total_seconds() / 86400.0)
            decay = 2.0 ** (-elapsed_days / cls.HALF_LIFE_DAYS)
            decay = min(max(decay, 0.0), 1.0)
            r = trust_state.positive_evidence_r * decay
            s = trust_state.negative_evidence_s * decay

        denominator = r + s + 2.0
        b = r / denominator
        d = s / denominator
        u = 2.0 / denominator
        t = b + 0.5 * u

        return TrustScoreResponse(
            agent_id=agent_id,
            trust=t,
            belief=b,
            disbelief=d,
            uncertainty=u,
            recent_risk=rr,
            positive_evidence=r,
            negative_evidence=s
        )
