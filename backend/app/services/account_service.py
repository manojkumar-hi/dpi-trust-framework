import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import issuer
from app.models.organization import Organization
from app.models.organization_administrator import OrganizationAdministrator
from app.models.organization_identity import OrganizationIdentity
from app.models.organization_identity_key import OrganizationIdentityKey
from app.models.revoked_auth_token import RevokedAuthToken
from app.schemas.account import OrganizationRegistrationRequest
from app.services.organization_key_service import save_private_key
from app.schemas.audit import AuditRecordCreate
from app.services.audit_service import AuditService

_HASH_ALGORITHM = "pbkdf2_sha256"
_HASH_ITERATIONS = 600_000


class DuplicateAdministratorError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return f"{_HASH_ALGORITHM}${_HASH_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != _HASH_ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.urlsafe_b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(base64.urlsafe_b64decode(expected), digest)
    except (ValueError, TypeError):
        return False


def register_organization(db: Session, request: OrganizationRegistrationRequest) -> tuple[Organization, OrganizationAdministrator]:
    email = _normalize_email(str(request.email))
    if db.scalar(select(OrganizationAdministrator).where(OrganizationAdministrator.email == email)):
        raise DuplicateAdministratorError

    email_domain = email.split("@", 1)[1]
    organization_slug = re.sub(r"[^a-z0-9]+", "-", request.organization_name.strip().lower()).strip("-") or "organization"
    domain = f"{organization_slug}-{uuid4().hex[:12]}.{email_domain}"
    organization = Organization(name=request.organization_name.strip(), domain=domain)
    administrator = OrganizationAdministrator(
        organization=organization,
        full_name=request.full_name.strip(),
        email=email,
        phone=request.phone.strip(),
        password_hash=hash_password(request.password),
    )
    db.add_all([organization, administrator])
    db.flush()

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    identity = OrganizationIdentity(
        organization_id=organization.id,
        did=f"did:web:{domain}",
        public_key=base64.b64encode(public_key).decode("ascii"),
    )
    identity.keys.append(
        OrganizationIdentityKey(
            verification_method=f"did:web:{domain}#key-1",
            public_key=identity.public_key,
            valid_from=datetime.now(timezone.utc),
        )
    )
    db.add(identity)
    AuditService.create_audit_record(
        db,
        AuditRecordCreate(
            event_category="IDENTITY",
            event_type="organization_registered",
            actor_organization_id=organization.id,
            resource_type="organization",
            resource_id=str(organization.id),
            event_metadata={"administrator_id": str(administrator.id)},
        ),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateAdministratorError from exc
    save_private_key(organization.id, private_key)
    db.refresh(organization)
    db.refresh(administrator)
    return organization, administrator


def authenticate_administrator(db: Session, email: str, password: str) -> tuple[Organization, OrganizationAdministrator]:
    administrator = db.scalar(
        select(OrganizationAdministrator).where(OrganizationAdministrator.email == _normalize_email(email))
    )
    if administrator is None or administrator.status != "active" or not verify_password(password, administrator.password_hash):
        raise InvalidCredentialsError
    organization = db.get(Organization, administrator.organization_id)
    if organization is None or organization.status != "active":
        raise InvalidCredentialsError
    return organization, administrator


def complete_organization_onboarding(db: Session, organization: Organization) -> bool:
    if organization.onboarding_completed:
        return False
    organization.onboarding_completed = True
    AuditService.create_audit_record(
        db,
        AuditRecordCreate(
            event_category="IDENTITY",
            event_type="organization_onboarding_completed",
            actor_organization_id=organization.id,
            resource_type="organization",
            resource_id=str(organization.id),
        ),
    )
    db.commit()
    db.refresh(organization)
    return True


def issue_administrator_token(organization: Organization, administrator: OrganizationAdministrator) -> str:
    return issuer.issue_token(
        subject=administrator.email,
        org_id=str(organization.id),
        admin_id=str(administrator.id),
        role="organization_admin",
    )


def revoke_token(db: Session, jti: str, expires_at: datetime) -> None:
    if not db.scalar(select(RevokedAuthToken).where(RevokedAuthToken.jti == jti)):
        db.add(RevokedAuthToken(jti=jti, expires_at=expires_at))
        db.commit()


def is_token_revoked(db: Session, jti: str) -> bool:
    return db.scalar(select(RevokedAuthToken).where(RevokedAuthToken.jti == jti)) is not None