"""add tool priority and auto-disable columns

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-03-22 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tool_registry', sa.Column('priority', sa.Integer(), nullable=True, server_default='50'))
    op.add_column('tool_registry', sa.Column('effectiveness_threshold', sa.Float(), nullable=True, server_default='20.0'))
    op.add_column('tool_registry', sa.Column('auto_disabled', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('tool_registry', 'auto_disabled')
    op.drop_column('tool_registry', 'effectiveness_threshold')
    op.drop_column('tool_registry', 'priority')
