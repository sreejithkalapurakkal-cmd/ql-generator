"""add evaboot discovery mode columns to pipeline_runs

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pipeline_runs', sa.Column('discovery_mode', sa.String(50), nullable=True, server_default='qlgen_only'))
    op.add_column('pipeline_runs', sa.Column('sales_navigator_url', sa.Text(), nullable=True))
    op.add_column('pipeline_runs', sa.Column('evaboot_extraction_id', sa.String(255), nullable=True))
    op.add_column('pipeline_runs', sa.Column('evaboot_credits_used', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('pipeline_runs', 'evaboot_credits_used')
    op.drop_column('pipeline_runs', 'evaboot_extraction_id')
    op.drop_column('pipeline_runs', 'sales_navigator_url')
    op.drop_column('pipeline_runs', 'discovery_mode')
