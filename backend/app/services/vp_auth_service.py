import base64
import logging
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.agent_identity import AgentIdentity
from app.models.agent_identity_key import AgentIdentityKey
from app.models.challenge import Challenge
from app.schemas.audit import AuditRecordCreate
from app.services.audit_service import AuditService
from app.services.vc_verification_service import verify_vc_jwt

logger = logging.getLogger(__name__)

# Constants
VP_REASON_VALID = "VALID"
VP_REASON_MALFORMED = "VP_MALFORMED"
VP_REASON_INVALID_SIGNATURE = "VP_INVALID_SIGNATURE"
VP_REASON_UNSUPPORTED_ALG = "VP_UNSUPPORTED_ALG"
VP_REASON_UNKNOWN_ISSUER = "VP_UNKNOWN_ISSUER"
VP_REASON_UNKNOWN_KID = "VP_UNKNOWN_KID"
VP_REASON_KEY_LIFECYCLE = "VP_KEY_LIFECYCLE"
VP_REASON_TEMPORAL_INVALID = "VP_TEMPORAL_INVALID"
VP_REASON_VC_INVALID = "VP_VC_INVALID"
VP_REASON_SUBJECT_MISMATCH = "VP_SUBJECT_MISMATCH"
VP_REASON_CHALLENGE_INVALID = "VP_CHALLENGE_INVALID"
VP_REASON_AUDIENCE_MISMATCH = "VP_AUDIENCE_MISMATCH"

_ALLOWED_ALGS = frozenset({"EdDSA"})
_CLOCK_SKEW = timedelta(seconds=60)

class VPAuthError(Exception):
    def __init__(self, reason_code: str, message: str, **kwargs):
        self.reason_code = reason_code
        self.message = message
        self.kwargs = kwargs
        super().__init__(f"{reason_code}: {message}")


def _audit(db: Session, event_type: str, decision: str, reason_code: str, actor_did: str | None = None, **kwargs):
    record = AuditRecordCreate(
        event_category="authentication",
        event_type=event_type,
        actor_did=actor_did,
        action_requested="vp_authentication",
        authorization_decision=decision,
        reason_code=reason_code,
        event_details=kwargs
    )
    AuditService.create_audit_record(db, record)


def create_challenge(db: Session, expires_in_seconds: int = 300) -> Challenge:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    challenge = Challenge(
        nonce=secrets.token_urlsafe(32),
        audience=settings.verifier_did,
        issued_at=now,
        expires_at=now + timedelta(seconds=expires_in_seconds)
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    _audit(db, "challenge_created", "ALLOW", "SUCCESS", event_details={"challenge_id": str(challenge.id), "audience": challenge.audience})
    return challenge


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def verify_vp_and_consume_challenge(db: Session, challenge_id: UUID, vp_jwt: str) -> AgentIdentity:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    actor_did = None

    try:
        # 1. Parse VP safely
        try:
            unverified_header = jwt.get_unverified_header(vp_jwt)
            unverified_payload = jwt.decode(vp_jwt, options={"verify_signature": False})
        except jwt.DecodeError:
            raise VPAuthError(VP_REASON_MALFORMED, "VP JWT is malformed")

        # 2. Extract candidate issuer/kid
        alg = unverified_header.get("alg")
        if alg not in _ALLOWED_ALGS:
            raise VPAuthError(VP_REASON_UNSUPPORTED_ALG, f"Algorithm {alg} not supported")

        kid = unverified_header.get("kid")
        if not kid:
            raise VPAuthError(VP_REASON_UNKNOWN_KID, "kid is missing")

        iss = unverified_payload.get("iss")
        if not iss:
            raise VPAuthError(VP_REASON_MALFORMED, "iss claim is missing")
        actor_did = iss

        # 3. Resolve candidate Agent DID/key
        agent_identity: AgentIdentity | None = db.scalar(
            select(AgentIdentity)
            .options(selectinload(AgentIdentity.keys), selectinload(AgentIdentity.agent))
            .where(AgentIdentity.did == iss)
        )
        if not agent_identity:
            raise VPAuthError(VP_REASON_UNKNOWN_ISSUER, f"Agent DID {iss} not found")

        agent_key = next((k for k in agent_identity.keys if k.verification_method == kid), None)
        if not agent_key:
            raise VPAuthError(VP_REASON_UNKNOWN_KID, f"Key {kid} not found for {iss}")

        raw_iat = unverified_payload.get("iat")
        if not raw_iat:
            raise VPAuthError(VP_REASON_MALFORMED, "iat claim is missing")
        vp_iat = datetime.fromtimestamp(raw_iat, tz=timezone.utc)

        key_valid_from = _ensure_utc(agent_key.valid_from)
        if vp_iat < key_valid_from - _CLOCK_SKEW:
            raise VPAuthError(VP_REASON_KEY_LIFECYCLE, "VP iat is before key valid_from")
        if agent_key.valid_until and vp_iat > _ensure_utc(agent_key.valid_until) + _CLOCK_SKEW:
            raise VPAuthError(VP_REASON_KEY_LIFECYCLE, "VP iat is after key valid_until")

        # 4. Verify VP signature
        try:
            public_key_bytes = base64.b64decode(agent_key.public_key)
            ed_public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except Exception:
            raise VPAuthError(VP_REASON_INVALID_SIGNATURE, "Failed to load public key")

        try:
            verified_payload = jwt.decode(
                vp_jwt,
                ed_public_key,
                algorithms=["EdDSA"],
                audience=settings.verifier_did,
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "leeway": _CLOCK_SKEW.total_seconds(),
                }
            )
        except jwt.ExpiredSignatureError:
            raise VPAuthError(VP_REASON_TEMPORAL_INVALID, "VP has expired")
        except jwt.InvalidTokenError as e:
            raise VPAuthError(VP_REASON_INVALID_SIGNATURE, f"VP signature/claim invalid: {e}")

        # 5. Extract and Validate embedded VC
        vp_claim = verified_payload.get("vp", {})
        vcs = vp_claim.get("verifiableCredential", [])
        if not vcs or not isinstance(vcs, list):
            raise VPAuthError(VP_REASON_MALFORMED, "Missing embedded VC")

        vc_jwt = vcs[0]
        vc_result = verify_vc_jwt(vc_jwt, db)
        if not vc_result.valid:
            raise VPAuthError(VP_REASON_VC_INVALID, f"Embedded VC is invalid: {vc_result.message}")

        # 6. Validate VP issuer == VC subject
        if vc_result.subject_did != iss:
            raise VPAuthError(VP_REASON_SUBJECT_MISMATCH, "VP issuer does not match VC subject")

        vp_nonce = verified_payload.get("nonce")
        vp_aud = verified_payload.get("aud")

        # 7. Begin DB Transaction to securely consume challenge
        try:
            # We must use with_for_update to atomically lock the row
            challenge = db.scalar(
                select(Challenge)
                .where(Challenge.id == challenge_id)
                .with_for_update()
            )

            if not challenge:
                raise VPAuthError(VP_REASON_CHALLENGE_INVALID, "Challenge not found")
            if challenge.consumed_at:
                raise VPAuthError(VP_REASON_CHALLENGE_INVALID, "Challenge already consumed")
            if _ensure_utc(challenge.expires_at) < now:
                raise VPAuthError(VP_REASON_CHALLENGE_INVALID, "Challenge expired")
            if vp_nonce != challenge.nonce:
                raise VPAuthError(VP_REASON_CHALLENGE_INVALID, "Nonce mismatch")
            if vp_aud != challenge.audience or challenge.audience != settings.verifier_did:
                raise VPAuthError(VP_REASON_AUDIENCE_MISMATCH, "Audience mismatch")

            # Mark consumed
            challenge.consumed_at = now
            _audit(db, "vp_authentication_succeeded", "ALLOW", VP_REASON_VALID, actor_did=iss)
            db.commit()

            return agent_identity

        except VPAuthError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise VPAuthError(VP_REASON_MALFORMED, str(e))

    except VPAuthError as e:
        _audit(db, "vp_authentication_failed", "DENY", e.reason_code, actor_did=actor_did, message=e.message)
        raise e
    except Exception as e:
        _audit(db, "vp_authentication_failed", "DENY", "INTERNAL_ERROR", actor_did=actor_did, message=str(e))
        raise VPAuthError("INTERNAL_ERROR", str(e))
