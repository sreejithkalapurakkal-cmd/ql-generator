"""add daily credit limit and expected result count

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-04-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'o5p6q7r8s9t0'
down_revision: Union[str, None] = 'n4o5p6q7r8s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('daily_credit_limit', sa.Integer(), nullable=True))
    op.add_column('pipeline_runs', sa.Column('expected_result_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('pipeline_runs', 'expected_result_count')
    op.drop_column('users', 'daily_credit_limit')
