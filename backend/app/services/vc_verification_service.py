import base64
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.verifiable_credential import VerifiableCredential
from app.schemas.vc_verification import VCVerificationResult

logger = logging.getLogger(__name__)

# ?? reason codes ??????????????????????????????????????????????????????????????
VALID = "VALID"
MALFORMED_VC = "MALFORMED_VC"
UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"
MISSING_KID = "MISSING_KID"
UNKNOWN_KID = "UNKNOWN_KID"
ISSUER_NOT_FOUND = "ISSUER_NOT_FOUND"
ISSUER_KEY_MISMATCH = "ISSUER_KEY_MISMATCH"
SIGNATURE_INVALID = "SIGNATURE_INVALID"
KEY_NOT_VALID_AT_ISSUANCE = "KEY_NOT_VALID_AT_ISSUANCE"
CREDENTIAL_EXPIRED = "CREDENTIAL_EXPIRED"
CREDENTIAL_NOT_YET_VALID = "CREDENTIAL_NOT_YET_VALID"
SUBJECT_MISMATCH = "SUBJECT_MISMATCH"
JTI_MISMATCH = "JTI_MISMATCH"
INVALID_VC_STRUCTURE = "INVALID_VC_STRUCTURE"
CREDENTIAL_REVOKED = "CREDENTIAL_REVOKED"

_ALLOWED_ALGORITHMS = frozenset({"EdDSA"})
_REJECTED_ALGORITHMS = frozenset({
    "none", "HS256", "HS384", "HS512",
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
})

# Small clock-skew tolerance (consistent with Module 13)
_CLOCK_SKEW = timedelta(seconds=30)


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC).

    SQLite returns tz-naive datetimes; PostgreSQL returns tz-aware.
    Consistently coerce to UTC for comparison.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _fail(reason_code: str, message: str, **partial) -> VCVerificationResult:
    return VCVerificationResult(
        valid=False,
        reason_code=reason_code,
        signature_status=partial.pop("signature_status", "invalid"),
        message=message,
        **partial,
    )


def verify_vc_jwt(vc_jwt: str, db: Session) -> VCVerificationResult:
    now = datetime.now(timezone.utc)

    # ?? Step 1: parse JWT header (unverified, for key selection only) ?????????
    try:
        unverified_header = jwt.get_unverified_header(vc_jwt)
    except jwt.DecodeError:
        return _fail(MALFORMED_VC, "JWT is malformed and cannot be decoded")

    alg = unverified_header.get("alg", "")
    kid = unverified_header.get("kid", "")

    # ?? Step 2: algorithm whitelist ???????????????????????????????????????????
    if alg in _REJECTED_ALGORITHMS or alg not in _ALLOWED_ALGORITHMS:
        return _fail(
            UNSUPPORTED_ALGORITHM,
            f"Algorithm '{alg}' is not supported. Only EdDSA is accepted.",
            signature_status="invalid",
        )

    # ?? Step 3: kid must be present ???????????????????????????????????????????
    if not kid:
        return _fail(MISSING_KID, "JWT header is missing 'kid'")

    # ?? Step 4: extract unverified payload (only for DID resolution) ??????????
    try:
        unverified_payload = jwt.decode(vc_jwt, options={"verify_signature": False})
    except jwt.DecodeError:
        return _fail(MALFORMED_VC, "JWT payload is malformed")

    iss = unverified_payload.get("iss", "")
    if not iss:
        return _fail(MALFORMED_VC, "JWT is missing 'iss' claim")

    # ?? Step 5: resolve issuer DID ????????????????????????????????????????????
    issuer_identity: OrganizationIdentity | None = db.scalar(
        select(OrganizationIdentity)
        .options(selectinload(OrganizationIdentity.keys))
        .where(OrganizationIdentity.did == iss)
    )
    if issuer_identity is None:
        return _fail(ISSUER_NOT_FOUND, f"Issuer DID '{iss}' could not be resolved", issuer_did=iss)

    # ?? Step 6: resolve signing key ???????????????????????????????????????????
    # kid must belong to this issuer; unknown kid from any other org also fails closed
    signing_key: OrganizationIdentityKey | None = next(
        (k for k in issuer_identity.keys if k.verification_method == kid), None
    )
    if signing_key is None:
        # Double-check: if kid exists for a *different* issuer that is a different error
        cross_key: OrganizationIdentityKey | None = db.scalar(
            select(OrganizationIdentityKey).where(
                OrganizationIdentityKey.verification_method == kid
            )
        )
        if cross_key is not None:
            return _fail(
                ISSUER_KEY_MISMATCH,
                f"Key '{kid}' belongs to a different issuer DID",
                issuer_did=iss,
                kid=kid,
            )
        return _fail(UNKNOWN_KID, f"Key '{kid}' is not known for issuer '{iss}'", issuer_did=iss, kid=kid)

    # ?? Step 7: historical key lifecycle ??????????????????????????????????????
    # Derive iat from unverified payload (will be verified again after signature)
    raw_iat = unverified_payload.get("iat")
    if raw_iat is None:
        return _fail(MALFORMED_VC, "JWT is missing 'iat' claim", issuer_did=iss, kid=kid)
    try:
        issued_at_dt = datetime.fromtimestamp(raw_iat, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return _fail(MALFORMED_VC, "JWT 'iat' value is invalid", issuer_did=iss, kid=kid)

    key_valid_from = _ensure_utc(signing_key.valid_from)
    key_valid_until = _ensure_utc(signing_key.valid_until) if signing_key.valid_until else None
    if issued_at_dt < key_valid_from - _CLOCK_SKEW:
        return _fail(
            KEY_NOT_VALID_AT_ISSUANCE,
            f"Credential issuance time ({issued_at_dt.isoformat()}) is before the key's validity start",
            issuer_did=iss,
            kid=kid,
            issued_at=issued_at_dt,
            signature_status="key_lifecycle",
        )
    if key_valid_until is not None and issued_at_dt > key_valid_until + _CLOCK_SKEW:
        return _fail(
            KEY_NOT_VALID_AT_ISSUANCE,
            f"Credential issuance time ({issued_at_dt.isoformat()}) is after the key's validity end",
            issuer_did=iss,
            kid=kid,
            issued_at=issued_at_dt,
            signature_status="key_lifecycle",
        )

    # ?? Step 8: cryptographic verification ????????????????????????????????????
    try:
        public_key_bytes = base64.b64decode(signing_key.public_key)
        ed_public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except Exception:
        return _fail(SIGNATURE_INVALID, "Failed to load issuer public key", issuer_did=iss, kid=kid)

    # After this point ALL trust decisions are post-verification
    try:
        verified_payload = jwt.decode(
            vc_jwt,
            ed_public_key,
            algorithms=["EdDSA"],
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "leeway": _CLOCK_SKEW.total_seconds(),
            },
        )
    except jwt.ExpiredSignatureError:
        exp_val = unverified_payload.get("exp")
        expires_at_dt = datetime.fromtimestamp(exp_val, tz=timezone.utc) if exp_val else None
        return _fail(
            CREDENTIAL_EXPIRED,
            "Credential has expired",
            issuer_did=iss,
            subject_did=unverified_payload.get("sub"),
            kid=kid,
            issued_at=issued_at_dt,
            expires_at=expires_at_dt,
            signature_status="expired",
        )
    except jwt.ImmatureSignatureError:
        return _fail(
            CREDENTIAL_NOT_YET_VALID,
            "Credential is not yet valid (nbf is in the future)",
            issuer_did=iss,
            kid=kid,
            issued_at=issued_at_dt,
            signature_status="invalid",
        )
    except jwt.InvalidSignatureError:
        return _fail(SIGNATURE_INVALID, "Ed25519 signature verification failed", issuer_did=iss, kid=kid)
    except jwt.InvalidTokenError:
        return _fail(SIGNATURE_INVALID, "JWT signature verification failed", issuer_did=iss, kid=kid)

    # ?? Step 9: validate W3C VC structure ?????????????????????????????????????
    vc_claim = verified_payload.get("vc")
    if not isinstance(vc_claim, dict):
        return _fail(
            INVALID_VC_STRUCTURE,
            "JWT does not contain a valid 'vc' claim",
            issuer_did=iss,
            kid=kid,
            issued_at=issued_at_dt,
            signature_status="valid",
        )

    vc_context = vc_claim.get("@context", [])
    vc_type = vc_claim.get("type", [])
    credential_subject = vc_claim.get("credentialSubject", {})

    if not vc_context or not isinstance(vc_context, list):
        return _fail(INVALID_VC_STRUCTURE, "VC '@context' is missing or invalid",
                     issuer_did=iss, kid=kid, issued_at=issued_at_dt, signature_status="valid")
    if not vc_type or not isinstance(vc_type, list) or "VerifiableCredential" not in vc_type:
        return _fail(INVALID_VC_STRUCTURE, "VC 'type' is missing or does not contain VerifiableCredential",
                     issuer_did=iss, kid=kid, issued_at=issued_at_dt, signature_status="valid")
    if not isinstance(credential_subject, dict):
        return _fail(INVALID_VC_STRUCTURE, "VC 'credentialSubject' is missing or invalid",
                     issuer_did=iss, kid=kid, issued_at=issued_at_dt, signature_status="valid")

    # ?? Step 10: subject consistency ??????????????????????????????????????????
    subject_did = verified_payload.get("sub", "")
    cs_id = credential_subject.get("id", "")
    if cs_id != subject_did:
        return _fail(
            SUBJECT_MISMATCH,
            f"credentialSubject.id ('{cs_id}') does not match JWT sub ('{subject_did}')",
            issuer_did=iss,
            subject_did=subject_did,
            kid=kid,
            issued_at=issued_at_dt,
            signature_status="valid",
        )

    # Derive structured fields from verified payload
    jti = verified_payload.get("jti")
    raw_exp = verified_payload.get("exp")
    expires_at_dt = datetime.fromtimestamp(raw_exp, tz=timezone.utc) if raw_exp else None

    # Derive credential type from vc.type (last element after VerifiableCredential)
    extra_types = [t for t in vc_type if t != "VerifiableCredential"]
    credential_type = extra_types[0] if extra_types else "VerifiableCredential"

    # ?? Step 11: optional local DB lookup ?????????????????????????????????????
    local_credential = None
    local_status = None
    fabric_transaction_id = None
    if jti:
        try:
            jti_uuid = UUID(jti)
            local_credential = db.get(VerifiableCredential, jti_uuid)
        except (ValueError, AttributeError):
            local_credential = None

    if local_credential is not None:
        # Update expired status in DB if applicable (non-blocking)
        if (
            local_credential.status == "active"
            and local_credential.expires_at is not None
            and _ensure_utc(local_credential.expires_at) <= now
        ):
            local_credential.status = "expired"
            try:
                db.commit()
            except Exception:
                db.rollback()

        local_status = local_credential.status
        fabric_transaction_id = getattr(local_credential, 'transaction_id', None)

        # Verify jti matches local credential id (they should be equal by construction)
        if str(local_credential.id) != jti:
            return _fail(
                JTI_MISMATCH,
                "JWT jti does not match the local credential ID",
                issuer_did=iss,
                subject_did=subject_did,
                credential_type=credential_type,
                jti=jti,
                kid=kid,
                issued_at=issued_at_dt,
                expires_at=expires_at_dt,
                vc_context=vc_context,
                vc_type=vc_type,
                credential_subject=credential_subject,
                local_credential_id=local_credential.id,
                local_status=local_status,
                signature_status="valid",
            )

        # Fabric/revocation status supplements cryptographic validity but does not replace it
        if local_status == "revoked":
            return VCVerificationResult(
                valid=False,
                reason_code=CREDENTIAL_REVOKED,
                issuer_did=iss,
                subject_did=subject_did,
                credential_type=credential_type,
                jti=jti,
                issued_at=issued_at_dt,
                expires_at=expires_at_dt,
                kid=kid,
                signature_status="valid",  # signature is valid; lifecycle is not
                vc_context=vc_context,
                vc_type=vc_type,
                credential_subject=credential_subject,
                local_credential_id=local_credential.id,
                local_status=local_status,
                fabric_transaction_id=fabric_transaction_id,
                message="Credential has been revoked",
            )

    # ?? VALID ?????????????????????????????????????????????????????????????????
    return VCVerificationResult(
        valid=True,
        reason_code=VALID,
        issuer_did=iss,
        subject_did=subject_did,
        credential_type=credential_type,
        jti=jti,
        issued_at=issued_at_dt,
        expires_at=expires_at_dt,
        kid=kid,
        signature_status="valid",
        vc_context=vc_context,
        vc_type=vc_type,
        credential_subject=credential_subject,
        local_credential_id=local_credential.id if local_credential else None,
        local_status=local_status,
        fabric_transaction_id=fabric_transaction_id,
        message="Credential is cryptographically valid and all claims are consistent",
    )
