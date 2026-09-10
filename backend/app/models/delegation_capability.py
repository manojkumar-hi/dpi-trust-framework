from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.delegation import Delegation


class DelegationCapability(Base):
    __tablename__ = "delegation_capabilities"
    __table_args__ = (Index("ix_delegation_capabilities_code", "capability_code"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    delegation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("delegations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_code: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    delegation: Mapped["Delegation"] = relationship(back_populates="capabilities")