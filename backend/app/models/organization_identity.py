from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.organization_identity_key import OrganizationIdentityKey
    from app.models.organization import Organization


class OrganizationIdentity(Base):
    __tablename__ = "organization_identities"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_organization_identities_organization_id"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    did: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    public_key: Mapped[str] = mapped_column(String(500), nullable=False)
    key_algorithm: Mapped[str] = mapped_column(String(100), nullable=False, default="Ed25519")
    authentication_issuer: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    authentication_subject: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="identity")
    keys: Mapped[list["OrganizationIdentityKey"]] = relationship(
        back_populates="organization_identity",
        cascade="all, delete-orphan",
        order_by="OrganizationIdentityKey.created_at",
    )
