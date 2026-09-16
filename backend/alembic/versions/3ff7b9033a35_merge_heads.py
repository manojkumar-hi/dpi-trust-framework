"""merge heads

Revision ID: 3ff7b9033a35
Revises: 8e837030c86e, ac11ca929663
Create Date: 2026-09-16 18:40:02.068503
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '3ff7b9033a35'
down_revision: Union[str, Sequence[str], None] = ('8e837030c86e', 'ac11ca929663')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass