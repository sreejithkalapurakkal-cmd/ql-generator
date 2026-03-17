"""add_promoted_column_to_companies

Revision ID: d4b2e9f1a3c7
Revises: c3a1f8b9d2e4
Create Date: 2026-03-08 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4b2e9f1a3c7'
down_revision: Union[str, None] = 'c3a1f8b9d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('promoted', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'promoted')
