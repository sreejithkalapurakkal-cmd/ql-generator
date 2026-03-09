"""add tool registry table

Revision ID: e5f3a7b2c8d1
Revises: d4b2e9f1a3c7
Create Date: 2026-03-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f3a7b2c8d1'
down_revision: Union[str, None] = 'd4b2e9f1a3c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tool_registry',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('requires_api_key', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('api_key_env_var', sa.String(100), nullable=True),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('health_status', sa.String(50), server_default=sa.text("'unknown'")),
        sa.Column('last_health_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_health_message', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_tool_registry_tool_name', 'tool_registry', ['tool_name'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_tool_registry_tool_name', table_name='tool_registry')
    op.drop_table('tool_registry')
