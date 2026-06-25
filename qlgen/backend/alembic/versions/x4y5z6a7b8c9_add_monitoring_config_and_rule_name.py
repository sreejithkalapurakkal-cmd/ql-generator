"""add monitoring_config to company_kb and custom_rule_name to signal_events

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-05-18 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'x4y5z6a7b8c9'
down_revision = 'w3x4y5z6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'company_knowledge_base',
        sa.Column('monitoring_config', JSONB, server_default='{}'),
    )
    op.add_column(
        'signal_events',
        sa.Column('custom_rule_name', sa.String(255)),
    )
    op.add_column(
        'users',
        sa.Column('settings', JSONB, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('users', 'settings')
    op.drop_column('signal_events', 'custom_rule_name')
    op.drop_column('company_knowledge_base', 'monitoring_config')
