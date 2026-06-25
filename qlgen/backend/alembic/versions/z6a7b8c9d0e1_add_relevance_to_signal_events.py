"""add relevance validity columns to signal_events

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-06-25 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'z6a7b8c9d0e1'
down_revision = 'y5z6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable on purpose: existing rows stay NULL (= "not yet checked", still visible)
    # until the backfill job evaluates them. Non-destructive.
    op.add_column('signal_events', sa.Column('is_relevant', sa.Boolean()))
    op.add_column('signal_events', sa.Column('relevance_reason', sa.String(length=500)))
    op.add_column('signal_events', sa.Column('relevance_checked_at', sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column('signal_events', 'relevance_checked_at')
    op.drop_column('signal_events', 'relevance_reason')
    op.drop_column('signal_events', 'is_relevant')
