"""add_copilot_chat_tables_and_embeddings

Revision ID: c3a1f8b9d2e4
Revises: 526a00746466
Create Date: 2026-03-05 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = 'c3a1f8b9d2e4'
down_revision: Union[str, None] = '526a00746466'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('page_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_calls', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('page_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_chat_messages_session_id', 'chat_messages', ['session_id'])

    # Add embedding column to companies table
    op.add_column('companies', sa.Column('embedding', Vector(1024), nullable=True))

    # Create HNSW index for fast cosine similarity search
    op.execute(
        "CREATE INDEX idx_companies_embedding ON companies "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_companies_embedding")
    op.drop_column('companies', 'embedding')
    op.drop_index('idx_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
