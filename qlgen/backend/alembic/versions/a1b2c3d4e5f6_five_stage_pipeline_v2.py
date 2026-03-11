"""five stage pipeline v2 - truncate data, create company_stage_results, add signal columns, drop bant_scores

Revision ID: a1b2c3d4e5f6
Revises: f6a4b8c3d9e2
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f6a4b8c3d9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Truncate all pipeline data (clean break for v2)
    op.execute("TRUNCATE pipeline_logs, bant_scores, contacts, companies, pipeline_runs CASCADE")

    # 2. Drop bant_scores table (replaced by company_stage_results)
    op.drop_table('bant_scores')

    # 3. Create company_stage_results table
    op.create_table(
        'company_stage_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('score', sa.Float, nullable=True),
        sa.Column('reasoning', sa.Text, nullable=True),
        sa.Column('evidence', postgresql.JSONB, nullable=True),
        sa.Column('user_override', sa.Boolean, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_company_stage_results_company_id', 'company_stage_results', ['company_id'])
    op.create_index('ix_company_stage_results_stage', 'company_stage_results', ['stage'])

    # 4. Add new columns to companies table
    op.add_column('companies', sa.Column('current_stage', sa.String(50), nullable=True))
    op.add_column('companies', sa.Column('budget_signal_score', sa.Float, nullable=True))
    op.add_column('companies', sa.Column('urgency_signal_score', sa.Float, nullable=True))
    op.add_column('companies', sa.Column('final_score', sa.Float, nullable=True))
    op.add_column('companies', sa.Column('final_rank', sa.Integer, nullable=True))
    op.add_column('companies', sa.Column('data_freshness', sa.DateTime(timezone=True), nullable=True))
    op.add_column('companies', sa.Column('cached_from_run_id', postgresql.UUID(as_uuid=True), nullable=True))

    # 5. Add signal_mode and signal_phase to pipeline_runs
    op.add_column('pipeline_runs', sa.Column('signal_mode', sa.String(50), nullable=True))
    op.add_column('pipeline_runs', sa.Column('signal_phase', sa.String(50), nullable=True))

    # 6. Create index on companies.website for cache lookups
    op.execute("CREATE INDEX ix_companies_website ON companies (lower(website))")

    # 7. Remove bant_score relationship FK from companies (the bant_scores table is gone)
    #    The company_id FK in bant_scores was already dropped with the table.


def downgrade() -> None:
    # Remove new indexes
    op.drop_index('ix_companies_website', 'companies')

    # Remove new columns from pipeline_runs
    op.drop_column('pipeline_runs', 'signal_phase')
    op.drop_column('pipeline_runs', 'signal_mode')

    # Remove new columns from companies
    op.drop_column('companies', 'cached_from_run_id')
    op.drop_column('companies', 'data_freshness')
    op.drop_column('companies', 'final_rank')
    op.drop_column('companies', 'final_score')
    op.drop_column('companies', 'urgency_signal_score')
    op.drop_column('companies', 'budget_signal_score')
    op.drop_column('companies', 'current_stage')

    # Drop company_stage_results
    op.drop_index('ix_company_stage_results_stage', 'company_stage_results')
    op.drop_index('ix_company_stage_results_company_id', 'company_stage_results')
    op.drop_table('company_stage_results')

    # Recreate bant_scores table
    op.create_table(
        'bant_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('companies.id'), nullable=True),
        sa.Column('contact_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contacts.id'), nullable=True),
        sa.Column('budget_score', sa.Integer),
        sa.Column('budget_reason', sa.Text),
        sa.Column('budget_sources', postgresql.JSONB),
        sa.Column('authority_score', sa.Integer),
        sa.Column('authority_reason', sa.Text),
        sa.Column('authority_sources', postgresql.JSONB),
        sa.Column('need_score', sa.Integer),
        sa.Column('need_reason', sa.Text),
        sa.Column('need_sources', postgresql.JSONB),
        sa.Column('timing_score', sa.Integer),
        sa.Column('timing_reason', sa.Text),
        sa.Column('timing_sources', postgresql.JSONB),
        sa.Column('total_score', sa.Integer),
        sa.Column('overall_summary', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
