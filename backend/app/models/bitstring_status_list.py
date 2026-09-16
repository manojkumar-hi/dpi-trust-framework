from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text, func, Index
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BitstringStatusList(Base):
    __tablename__ = "bitstring_status_lists"
    __table_args__ = (
        Index("ix_bitstring_status_lists_issuer_did", "issuer_did"),
        Index("ix_bitstring_status_lists_status_purpose", "status_purpose"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    issuer_did: Mapped[str] = mapped_column(String(500), nullable=False)
    status_purpose: Mapped[str] = mapped_column(String(50), nullable=False, default="revocation")
    bitstring: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_list_vc_jwt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
