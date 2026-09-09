from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate


class DuplicateOrganizationDomainError(Exception):
    pass


def create_organization(db: Session, organization_data: OrganizationCreate) -> Organization:
    organization = Organization(**organization_data.model_dump())
    db.add(organization)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateOrganizationDomainError from exc
    db.refresh(organization)
    return organization


def get_organizations(db: Session) -> list[Organization]:
    return list(db.scalars(select(Organization).order_by(Organization.created_at)).all())


def get_organization(db: Session, organization_id: UUID) -> Organization | None:
    return db.get(Organization, organization_id)
