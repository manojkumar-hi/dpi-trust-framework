import asyncio
import logging
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.outbox import OutboxEvent
from app.models.verifiable_credential import VerifiableCredential
from app.models.delegation import Delegation
from app.services.fabric_ledger_client import FabricLedgerClient

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
LOCK_TIMEOUT_SECONDS = 300  # 5 minutes


class OutboxWorker:
    def __init__(self):
        self._running = False
        self._task = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        if self._task:
            await self._task
            self._task = None

    async def _run_loop(self):
        logger.info("Outbox worker started")
        while self._running:
            try:
                processed_count = await self._process_batch()
                if processed_count == 0:
                    # Sleep if no events to process
                    await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in outbox worker loop: {e}")
                await asyncio.sleep(5.0)

    async def _process_batch(self) -> int:
        processed = 0
        with SessionLocal() as db:
            # 1. Claim events
            # Use SKIP LOCKED to avoid blocking concurrent workers
            stmt = text("""
                SELECT id FROM outbox_events 
                WHERE status IN ('PENDING', 'FAILED') 
                AND next_attempt_at <= NOW() 
                AND (locked_until IS NULL OR locked_until <= NOW()) 
                FOR UPDATE SKIP LOCKED 
                LIMIT 10
            """)
            
            rows = db.execute(stmt).fetchall()
            if not rows:
                return 0
                
            event_ids = [row[0] for row in rows]
            
            # Lock them in the DB
            lock_until = datetime.now(timezone.utc) + timedelta(seconds=LOCK_TIMEOUT_SECONDS)
            events = db.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_(event_ids))
            ).scalars().all()
            
            for event in events:
                event.status = "PROCESSING"
                event.locked_until = lock_until
                event.attempt_count += 1
                
            db.commit()
            
            # 2. Process events
            fabric_client = FabricLedgerClient()
            try:
                for event in events:
                    if not self._running:
                        break
                        
                    try:
                        tx_id = await self._process_event(db, event, fabric_client)
                        event.status = "COMPLETED"
                        event.locked_until = None
                        event.fabric_transaction_id = tx_id
                        
                        # Update the corresponding business object
                        self._update_business_entity(db, event, tx_id)
                        
                        db.commit()
                        processed += 1
                        logger.info(f"Successfully processed outbox event {event.id}")
                    except Exception as e:
                        db.rollback()
                        logger.warning(f"Failed to process outbox event {event.id}: {e}")
                        
                        # Use a separate transaction to update the failure status
                        with SessionLocal() as fail_db:
                            fail_event = fail_db.get(OutboxEvent, event.id)
                            if fail_event:
                                if fail_event.attempt_count >= MAX_ATTEMPTS:
                                    fail_event.status = "DEAD_LETTER"
                                    fail_event.locked_until = None
                                    fail_event.last_error = str(e)
                                else:
                                    fail_event.status = "FAILED"
                                    fail_event.locked_until = None
                                    fail_event.last_error = str(e)
                                    # Exponential backoff: 2^attempts * 5 seconds
                                    backoff_seconds = (2 ** fail_event.attempt_count) * 5
                                    fail_event.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                                fail_db.commit()
            finally:
                await fabric_client.close()
                
        return processed

    async def _process_event(self, db: Session, event: OutboxEvent, client: FabricLedgerClient) -> str | None:
        p = event.payload
        tx_id = None
        
        if event.event_type == "CREDENTIAL_ISSUED":
            res = await client.issue_credential(
                credential_id=p["credentialId"],
                credential_type=p["credentialType"],
                issuer_did=p["issuerDid"],
                subject_did=p["subjectDid"],
                credential_hash=p["credentialHash"],
                issued_at=p["issuedAt"]
            )
            tx_id = res.get("transaction_id")
            
        elif event.event_type == "CREDENTIAL_REVOKED":
            res = await client.revoke_credential(
                credential_id=p["credentialId"],
                reason=p["reason"],
                revoked_at=p["revokedAt"]
            )
            tx_id = res.get("transaction_id")
            
        elif event.event_type == "DELEGATION_ISSUED":
            res = await client.issue_delegation(
                delegation_id=p["delegationId"],
                delegator_did=p["delegatorDid"],
                delegatee_did=p["delegateeDid"],
                canonical_hash=p["canonicalHash"],
                issued_at=p["issuedAt"],
                expires_at=p["expiresAt"]
            )
            tx_id = res.get("transaction_id")
            
        elif event.event_type == "DELEGATION_REVOKED":
            res = await client.revoke_delegation(
                delegation_id=p["delegationId"],
                reason=p["reason"],
                revoked_at=p["revokedAt"]
            )
            tx_id = res.get("transaction_id")
        else:
            raise ValueError(f"Unknown event_type: {event.event_type}")
            
        return tx_id

    def _update_business_entity(self, db: Session, event: OutboxEvent, tx_id: str | None):
        if not tx_id:
            return
            
        if event.event_type in ("CREDENTIAL_ISSUED", "CREDENTIAL_REVOKED"):
            cred = db.get(VerifiableCredential, event.aggregate_id)
            if cred:
                cred.transaction_id = tx_id
        elif event.event_type in ("DELEGATION_ISSUED", "DELEGATION_REVOKED"):
            delegation = db.get(Delegation, event.aggregate_id)
            if delegation:
                delegation.fabric_transaction_id = tx_id

# Global instance
outbox_worker = OutboxWorker()
