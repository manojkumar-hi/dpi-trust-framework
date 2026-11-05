"""add organization onboarding state

Revision ID: 6b2c3d4e5f6a
Revises: 5a1f4b7c8d9e
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6b2c3d4e5f6a"
down_revision: Union[str, Sequence[str], None] = "5a1f4b7c8d9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("onboarding_completed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(
        sa.text(
            "UPDATE organizations SET onboarding_completed = TRUE "
            "WHERE EXISTS (SELECT 1 FROM agents WHERE agents.organization_id = organizations.id)"
        )
    )


def downgrade() -> None:
    op.drop_column("organizations", "onboarding_completed")