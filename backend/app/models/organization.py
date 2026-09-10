from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.delegation import Delegation
    from app.models.organization_identity import OrganizationIdentity
    from app.models.verifiable_credential import VerifiableCredential


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    agents: Mapped[list["Agent"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    identity: Mapped["OrganizationIdentity | None"] = relationship(
        back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )
    issued_credentials: Mapped[list["VerifiableCredential"]] = relationship(
        back_populates="issuer_organization"
    )
    outgoing_delegations: Mapped[list["Delegation"]] = relationship(
        back_populates="delegator_organization",
        foreign_keys="Delegation.delegator_organization_id",
    )
