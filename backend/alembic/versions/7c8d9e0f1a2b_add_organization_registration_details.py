"""add organization registration details

Revision ID: 7c8d9e0f1a2b
Revises: 6b2c3d4e5f6a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c8d9e0f1a2b"
down_revision: Union[str, Sequence[str], None] = "6b2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("organization_type", sa.String(length=50), nullable=True))
    op.add_column("organizations", sa.Column("cin", sa.String(length=21), nullable=True))
    op.add_column("organizations", sa.Column("official_email", sa.String(length=320), nullable=True))
    op.add_column("organizations", sa.Column("website", sa.String(length=500), nullable=True))
    op.create_unique_constraint("uq_organizations_cin", "organizations", ["cin"])


def downgrade() -> None:
    op.drop_constraint("uq_organizations_cin", "organizations", type_="unique")
    op.drop_column("organizations", "website")
    op.drop_column("organizations", "official_email")
    op.drop_column("organizations", "cin")
    op.drop_column("organizations", "organization_type")
