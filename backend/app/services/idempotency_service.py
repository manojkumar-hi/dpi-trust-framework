import hashlib
import json
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.idempotency import IdempotencyRecord


class IdempotencyService:
    @staticmethod
    def fingerprint_request(endpoint_path: str, payload: dict) -> str:
        """
        Creates a deterministic fingerprint of the request payload and endpoint path.
        Using SHA-256 and sorted JSON keys.
        """
        payload_str = json.dumps(payload, sort_keys=True)
        combined = f"{endpoint_path}:{payload_str}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def check_and_lock_idempotency(
        db: Session,
        organization_id: UUID,
        idempotency_key: str,
        endpoint_path: str,
        payload: dict,
    ) -> dict | None:
        """
        Checks for an existing idempotency record and returns the cached response if present.
        If a concurrent request is executing, blocks until it finishes.
        If no record exists, creates an in-progress record to lock the key for this transaction.
        """
        # Validate idempotency key bounds
        if not idempotency_key or len(idempotency_key) > 255:
            raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")

        fingerprint = IdempotencyService.fingerprint_request(endpoint_path, payload)

        # We use a nested transaction (savepoint) so we can catch IntegrityError
        # without failing the outer business transaction.
        try:
            with db.begin_nested():
                new_record = IdempotencyRecord(
                    id=uuid4(),
                    organization_id=organization_id,
                    idempotency_key=idempotency_key,
                    endpoint_path=endpoint_path,
                    request_fingerprint=fingerprint,
                    response_body=None,
                    response_status_code=None,
                )
                db.add(new_record)
        except IntegrityError:
            # The key already exists.
            # Because we were in a savepoint (begin_nested), the rollback has already occurred.
            pass
        else:
            # The INSERT succeeded. We hold the lock on this key until the outer transaction finishes.
            # Return None to indicate the business logic should proceed.
            return None

        # If we reach here, the record exists (or we hit a concurrent conflict that finished).
        # We fetch the existing record.
        existing_record = (
            db.query(IdempotencyRecord)
            .filter_by(organization_id=organization_id, idempotency_key=idempotency_key)
            .first()
        )

        if not existing_record:
            # This should theoretically not happen unless the record was deleted right after the IntegrityError,
            # or the transaction that inserted it rolled back. But wait!
            # If the concurrent transaction rolls back, we would have hit IntegrityError,
            # but then the record is gone!
            # We must retry the insert in this case.
            # To handle this cleanly, we can recurse once or use a while loop.
            return IdempotencyService.check_and_lock_idempotency(
                db, organization_id, idempotency_key, endpoint_path, payload
            )

        # Verify fingerprint to prevent accidental key reuse across different requests
        if existing_record.request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409, detail="Idempotency key already used with different payload or endpoint"
            )

        # Check if the record has a completed response
        if existing_record.response_status_code is None:
            # It's an in-progress record from a transaction that hasn't committed.
            # Wait, if we hit IntegrityError and it committed, we should see the response.
            # If we don't see the response, it might be that the other transaction committed an empty response?
            # Or perhaps we're in a read-committed isolation level and... wait, if the other transaction hasn't committed,
            # the `db.add` above would have BLOCKED until the other transaction completed.
            # If it committed, we see the response. If it rolled back, we wouldn't have found the record.
            # So if we see no response, something is wrong (e.g. they didn't update it).
            raise HTTPException(
                status_code=500, detail="Idempotency record in invalid state"
            )

        return existing_record.response_body

    @staticmethod
    def update_idempotency_response(
        db: Session,
        organization_id: UUID,
        idempotency_key: str,
        response_body: dict,
        status_code: int,
    ):
        """
        Updates the in-progress idempotency record with the final response.
        Must be called in the same transaction right before returning.
        """
        record = (
            db.query(IdempotencyRecord)
            .filter_by(organization_id=organization_id, idempotency_key=idempotency_key)
            .first()
        )
        if not record:
            raise ValueError(f"Idempotency record not found for key {idempotency_key}")
            
        record.response_body = response_body
        record.response_status_code = str(status_code)
        db.add(record)
        db.flush()
