"""add notes columns to signal_events

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-05-18 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'y5z6a7b8c9d0'
down_revision = 'x4y5z6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'signal_events',
        sa.Column('notes', sa.Text),
    )
    op.add_column(
        'signal_events',
        sa.Column('notes_updated_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column('signal_events', 'notes_updated_at')
    op.drop_column('signal_events', 'notes')
