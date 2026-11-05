"""add organization administrator auth

Revision ID: 5a1f4b7c8d9e
Revises: 3ff7b9033a35
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5a1f4b7c8d9e"
down_revision: Union[str, Sequence[str], None] = "1ea67b2d0ff0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_administrators",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_organization_administrators_organization_id", "organization_administrators", ["organization_id"])
    op.create_index("ix_organization_administrators_email", "organization_administrators", ["email"], unique=True)
    op.create_index("ix_organization_administrators_status", "organization_administrators", ["status"])
    op.create_table(
        "revoked_auth_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("jti", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("ix_revoked_auth_tokens_jti", "revoked_auth_tokens", ["jti"], unique=True)
    op.create_index("ix_revoked_auth_tokens_expires_at", "revoked_auth_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_revoked_auth_tokens_expires_at", table_name="revoked_auth_tokens")
    op.drop_index("ix_revoked_auth_tokens_jti", table_name="revoked_auth_tokens")
    op.drop_table("revoked_auth_tokens")
    op.drop_index("ix_organization_administrators_status", table_name="organization_administrators")
    op.drop_index("ix_organization_administrators_email", table_name="organization_administrators")
    op.drop_index("ix_organization_administrators_organization_id", table_name="organization_administrators")
    op.drop_table("organization_administrators")