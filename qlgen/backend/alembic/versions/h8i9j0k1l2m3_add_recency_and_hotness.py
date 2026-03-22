"""add recency and hotness columns to companies

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('recency_adjusted_budget_score', sa.Float, nullable=True))
    op.add_column('companies', sa.Column('recency_adjusted_urgency_score', sa.Float, nullable=True))
    op.add_column('companies', sa.Column('deal_hotness_score', sa.Float, nullable=True))
    op.add_column('companies', sa.Column('deal_hotness_tier', sa.String(10), nullable=True))
    op.add_column('companies', sa.Column('avg_evidence_age_months', sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'avg_evidence_age_months')
    op.drop_column('companies', 'deal_hotness_tier')
    op.drop_column('companies', 'deal_hotness_score')
    op.drop_column('companies', 'recency_adjusted_urgency_score')
    op.drop_column('companies', 'recency_adjusted_budget_score')
