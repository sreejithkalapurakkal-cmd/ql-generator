"""add disqualification_stage column to companies

Revision ID: f6a4b8c3d9e2
Revises: e5f3a7b2c8d1
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a4b8c3d9e2'
down_revision: Union[str, None] = 'e5f3a7b2c8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('disqualification_stage', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'disqualification_stage')
