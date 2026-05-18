"""add acted_on to signals

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-05-17 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('signal_events', sa.Column('is_acted_on', sa.Boolean(), server_default='false'))
    op.add_column('signal_events', sa.Column('acted_on_at', sa.DateTime(timezone=True)))

def downgrade() -> None:
    op.drop_column('signal_events', 'acted_on_at')
    op.drop_column('signal_events', 'is_acted_on')
