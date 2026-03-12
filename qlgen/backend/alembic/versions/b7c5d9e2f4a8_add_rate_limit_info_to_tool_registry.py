"""add_rate_limit_info_to_tool_registry

Revision ID: b7c5d9e2f4a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c5d9e2f4a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tool_registry', sa.Column('rate_limit_info', sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column('tool_registry', 'rate_limit_info')
