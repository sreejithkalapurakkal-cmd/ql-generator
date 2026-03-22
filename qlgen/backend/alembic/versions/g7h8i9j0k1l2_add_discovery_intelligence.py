"""add discovery intelligence tables

Revision ID: g7h8i9j0k1l2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'g1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'discovery_queries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pipeline_run_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('pipeline_runs.id'), nullable=True),
        sa.Column('icp_config_id', postgresql.UUID(as_uuid=True),
                   sa.ForeignKey('icp_configs.id'), nullable=True),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('country', sa.String(255), nullable=True),
        sa.Column('companies_found', sa.Integer(), default=0),
        sa.Column('companies_passed_stage2', sa.Integer(), default=0),
        sa.Column('avg_final_score', sa.Float(), nullable=True),
        sa.Column('effectiveness_score', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'tool_effectiveness',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('country', sa.String(255), nullable=True),
        sa.Column('total_companies_sourced', sa.Integer(), default=0),
        sa.Column('companies_passed_stage2', sa.Integer(), default=0),
        sa.Column('avg_final_score', sa.Float(), default=0.0),
        sa.Column('total_runs_used', sa.Integer(), default=0),
        sa.Column('effectiveness_score', sa.Float(), default=0.0),
        sa.Column('last_updated', sa.DateTime(timezone=True),
                   server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Add indexes for efficient querying
    op.create_index(
        'ix_discovery_queries_industry_country',
        'discovery_queries', ['industry', 'country'],
    )
    op.create_index(
        'ix_tool_effectiveness_industry_country',
        'tool_effectiveness', ['industry', 'country'],
    )


def downgrade() -> None:
    op.drop_index('ix_tool_effectiveness_industry_country')
    op.drop_index('ix_discovery_queries_industry_country')
    op.drop_table('tool_effectiveness')
    op.drop_table('discovery_queries')
