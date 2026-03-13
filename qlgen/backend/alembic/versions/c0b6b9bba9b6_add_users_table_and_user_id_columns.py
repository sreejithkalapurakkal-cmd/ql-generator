"""add_users_table_and_user_id_columns

Revision ID: c0b6b9bba9b6
Revises: b7c5d9e2f4a8
Create Date: 2026-03-12 14:56:33.341363

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c0b6b9bba9b6'
down_revision: Union[str, None] = 'b7c5d9e2f4a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('picture_url', sa.String(length=500), nullable=True),
        sa.Column('google_id', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Add user_id to chat_sessions
    op.add_column('chat_sessions', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)
    op.create_foreign_key('fk_chat_sessions_user_id', 'chat_sessions', 'users', ['user_id'], ['id'])

    # Add user_id to icp_configs
    op.add_column('icp_configs', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_icp_configs_user_id'), 'icp_configs', ['user_id'], unique=False)
    op.create_foreign_key('fk_icp_configs_user_id', 'icp_configs', 'users', ['user_id'], ['id'])

    # Add user_id to pipeline_runs
    op.add_column('pipeline_runs', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_pipeline_runs_user_id'), 'pipeline_runs', ['user_id'], unique=False)
    op.create_foreign_key('fk_pipeline_runs_user_id', 'pipeline_runs', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    # Remove user_id from pipeline_runs
    op.drop_constraint('fk_pipeline_runs_user_id', 'pipeline_runs', type_='foreignkey')
    op.drop_index(op.f('ix_pipeline_runs_user_id'), table_name='pipeline_runs')
    op.drop_column('pipeline_runs', 'user_id')

    # Remove user_id from icp_configs
    op.drop_constraint('fk_icp_configs_user_id', 'icp_configs', type_='foreignkey')
    op.drop_index(op.f('ix_icp_configs_user_id'), table_name='icp_configs')
    op.drop_column('icp_configs', 'user_id')

    # Remove user_id from chat_sessions
    op.drop_constraint('fk_chat_sessions_user_id', 'chat_sessions', type_='foreignkey')
    op.drop_index(op.f('ix_chat_sessions_user_id'), table_name='chat_sessions')
    op.drop_column('chat_sessions', 'user_id')

    # Drop users table
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
