"""add company_knowledge_base table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'company_knowledge_base',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        # Identity
        sa.Column('normalized_domain', sa.String(500), nullable=False),
        sa.Column('canonical_name', sa.String(500)),
        # Firmographics
        sa.Column('industry', sa.String(255)),
        sa.Column('sub_industry', sa.String(255)),
        sa.Column('country', sa.String(255)),
        sa.Column('city', sa.String(255)),
        sa.Column('state_region', sa.String(255)),
        sa.Column('employee_count', sa.Integer),
        sa.Column('revenue_estimate', sa.BigInteger),
        sa.Column('asset_value', sa.BigInteger),
        # Tech / Description
        sa.Column('tech_stack_json', JSONB),
        sa.Column('description', sa.Text),
        # Best-ever scores
        sa.Column('best_icp_match_score', sa.Float),
        sa.Column('best_budget_signal_score', sa.Float),
        sa.Column('best_urgency_signal_score', sa.Float),
        sa.Column('best_final_score', sa.Float),
        sa.Column('best_deal_hotness_score', sa.Float),
        sa.Column('best_deal_hotness_tier', sa.String(20)),
        # Contacts
        sa.Column('best_known_contacts', JSONB),
        # Provenance
        sa.Column('data_sources', JSONB),
        # Embedding
        sa.Column('embedding', Vector(1024)),
        # Metadata
        sa.Column('times_discovered', sa.Integer, server_default='1'),
        sa.Column('pipeline_run_ids', JSONB),
        sa.Column('first_discovered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_enriched_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Unique constraint on normalized_domain
    op.create_unique_constraint('uq_kb_normalized_domain', 'company_knowledge_base', ['normalized_domain'])

    # Btree indexes
    op.create_index('ix_kb_normalized_domain', 'company_knowledge_base', ['normalized_domain'])
    op.create_index('ix_kb_industry', 'company_knowledge_base', ['industry'])
    op.create_index('ix_kb_country', 'company_knowledge_base', ['country'])
    op.create_index('ix_kb_best_final_score', 'company_knowledge_base', ['best_final_score'])

    # HNSW vector index for cosine similarity
    op.execute("""
        CREATE INDEX ix_kb_embedding_hnsw
        ON company_knowledge_base
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.drop_index('ix_kb_embedding_hnsw', table_name='company_knowledge_base')
    op.drop_index('ix_kb_best_final_score', table_name='company_knowledge_base')
    op.drop_index('ix_kb_country', table_name='company_knowledge_base')
    op.drop_index('ix_kb_industry', table_name='company_knowledge_base')
    op.drop_index('ix_kb_normalized_domain', table_name='company_knowledge_base')
    op.drop_constraint('uq_kb_normalized_domain', 'company_knowledge_base', type_='unique')
    op.drop_table('company_knowledge_base')
