"""add signal tracking tables

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- tracking_lists --
    op.create_table(
        'tracking_lists',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('monitoring_config', postgresql.JSONB(), server_default='{}'),
        sa.Column('last_monitored_at', sa.DateTime(timezone=True)),
        sa.Column('next_monitor_due', sa.DateTime(timezone=True)),
        sa.Column('company_count', sa.Integer(), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_tracking_lists_user_id', 'tracking_lists', ['user_id'])

    # -- tracking_list_memberships --
    op.create_table(
        'tracking_list_memberships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tracking_list_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('tracking_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_kb_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('company_knowledge_base.id', ondelete='CASCADE'), nullable=False),
        sa.Column('added_from', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('outreach_status', sa.String(50), server_default='not_started'),
        sa.Column('outreach_history', postgresql.JSONB(), server_default='[]'),
        sa.Column('signal_heat_score', sa.Float(), server_default='0.0'),
        sa.Column('tags', postgresql.JSONB(), server_default='[]'),
        sa.Column('snoozed_until', sa.DateTime(timezone=True)),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint('uq_list_company', 'tracking_list_memberships',
                                ['tracking_list_id', 'company_kb_id'])
    op.create_index('ix_membership_list_id', 'tracking_list_memberships', ['tracking_list_id'])
    op.create_index('ix_membership_kb_id', 'tracking_list_memberships', ['company_kb_id'])
    op.create_index('ix_membership_outreach', 'tracking_list_memberships', ['outreach_status'])
    op.create_index('ix_membership_heat', 'tracking_list_memberships', ['signal_heat_score'])
    op.create_index('ix_membership_tags_gin', 'tracking_list_memberships', ['tags'],
                     postgresql_using='gin')

    # -- signal_events --
    op.create_table(
        'signal_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_kb_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('company_knowledge_base.id', ondelete='CASCADE'), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('signal_subtype', sa.String(100)),
        sa.Column('signal_category', sa.String(50)),
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('strength', sa.Float(), server_default='50.0'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('summary', sa.Text()),
        sa.Column('evidence', postgresql.JSONB()),
        sa.Column('source_tool', sa.String(100)),
        sa.Column('source_url', sa.String(500)),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('is_archived', sa.Boolean(), server_default='false'),
        sa.Column('is_dismissed', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_signal_company_created', 'signal_events', ['company_kb_id', 'created_at'])
    op.create_index('ix_signal_type', 'signal_events', ['signal_type'])
    op.create_index('ix_signal_priority', 'signal_events', ['priority'])
    op.create_index('ix_signal_expires', 'signal_events', ['expires_at'])
    op.create_index('ix_signal_archived', 'signal_events', ['is_archived'])

    # -- ingest_batches --
    op.create_table(
        'ingest_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('filename', sa.String(500)),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('column_mapping', postgresql.JSONB()),
        sa.Column('filter_config', postgresql.JSONB()),
        sa.Column('total_rows', sa.Integer(), server_default='0'),
        sa.Column('processed_rows', sa.Integer(), server_default='0'),
        sa.Column('matched_kb', sa.Integer(), server_default='0'),
        sa.Column('newly_created', sa.Integer(), server_default='0'),
        sa.Column('enriched_count', sa.Integer(), server_default='0'),
        sa.Column('filtered_count', sa.Integer(), server_default='0'),
        sa.Column('errors', postgresql.JSONB(), server_default='[]'),
        sa.Column('target_tracking_list_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('tracking_lists.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_ingest_user_created', 'ingest_batches', ['user_id', 'created_at'])
    op.create_index('ix_ingest_status', 'ingest_batches', ['status'])

    # -- notifications --
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('signal_event_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('signal_events.id', ondelete='SET NULL'), nullable=True),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('body', sa.Text()),
        sa.Column('link', sa.String(500)),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_notification_user_read_created', 'notifications',
                     ['user_id', 'is_read', 'created_at'])

    # -- tags --
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('color', sa.String(7), server_default="'#5C2D8F'"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_tags_user_id', 'tags', ['user_id'])
    op.create_unique_constraint('uq_user_tag_name', 'tags', ['user_id', 'name'])


def downgrade() -> None:
    op.drop_table('tags')
    op.drop_table('notifications')
    op.drop_table('ingest_batches')
    op.drop_table('signal_events')
    op.drop_table('tracking_list_memberships')
    op.drop_table('tracking_lists')
