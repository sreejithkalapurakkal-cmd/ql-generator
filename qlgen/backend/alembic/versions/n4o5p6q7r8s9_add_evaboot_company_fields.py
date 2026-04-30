"""add evaboot company fields and linkedin data

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-04-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, None] = 'm3n4o5p6q7r8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Company table: 11 new columns --
    op.add_column('companies', sa.Column('domain', sa.String(255), nullable=True))
    op.add_column('companies', sa.Column('linkedin_url', sa.String(500), nullable=True))
    op.add_column('companies', sa.Column('company_type', sa.String(100), nullable=True))
    op.add_column('companies', sa.Column('year_founded', sa.Integer(), nullable=True))
    op.add_column('companies', sa.Column('revenue_min', sa.BigInteger(), nullable=True))
    op.add_column('companies', sa.Column('revenue_max', sa.BigInteger(), nullable=True))
    op.add_column('companies', sa.Column('employee_growth_1y_pct', sa.Float(), nullable=True))
    op.add_column('companies', sa.Column('funding_stage', sa.String(100), nullable=True))
    op.add_column('companies', sa.Column('discovery_method', sa.String(50), server_default='qlgen', nullable=True))
    op.add_column('companies', sa.Column('headquarters_address', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('linkedin_data', postgresql.JSONB(), nullable=True))

    # Indexes on Company
    op.create_index('ix_companies_domain', 'companies', ['domain'])
    op.create_index('ix_companies_linkedin_url', 'companies', ['linkedin_url'])
    op.create_index('ix_companies_year_founded', 'companies', ['year_founded'])
    op.create_index('ix_companies_funding_stage', 'companies', ['funding_stage'])
    op.create_index('ix_companies_discovery_method', 'companies', ['discovery_method'])

    # -- CompanyKnowledgeBase table: 7 new columns --
    op.add_column('company_knowledge_base', sa.Column('linkedin_url', sa.String(500), nullable=True))
    op.add_column('company_knowledge_base', sa.Column('company_type', sa.String(100), nullable=True))
    op.add_column('company_knowledge_base', sa.Column('year_founded', sa.Integer(), nullable=True))
    op.add_column('company_knowledge_base', sa.Column('revenue_min', sa.BigInteger(), nullable=True))
    op.add_column('company_knowledge_base', sa.Column('revenue_max', sa.BigInteger(), nullable=True))
    op.add_column('company_knowledge_base', sa.Column('funding_stage', sa.String(100), nullable=True))
    op.add_column('company_knowledge_base', sa.Column('linkedin_data', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    # -- CompanyKnowledgeBase --
    op.drop_column('company_knowledge_base', 'linkedin_data')
    op.drop_column('company_knowledge_base', 'funding_stage')
    op.drop_column('company_knowledge_base', 'revenue_max')
    op.drop_column('company_knowledge_base', 'revenue_min')
    op.drop_column('company_knowledge_base', 'year_founded')
    op.drop_column('company_knowledge_base', 'company_type')
    op.drop_column('company_knowledge_base', 'linkedin_url')

    # -- Company indexes --
    op.drop_index('ix_companies_discovery_method', 'companies')
    op.drop_index('ix_companies_funding_stage', 'companies')
    op.drop_index('ix_companies_year_founded', 'companies')
    op.drop_index('ix_companies_linkedin_url', 'companies')
    op.drop_index('ix_companies_domain', 'companies')

    # -- Company columns --
    op.drop_column('companies', 'linkedin_data')
    op.drop_column('companies', 'headquarters_address')
    op.drop_column('companies', 'discovery_method')
    op.drop_column('companies', 'funding_stage')
    op.drop_column('companies', 'employee_growth_1y_pct')
    op.drop_column('companies', 'revenue_max')
    op.drop_column('companies', 'revenue_min')
    op.drop_column('companies', 'year_founded')
    op.drop_column('companies', 'company_type')
    op.drop_column('companies', 'linkedin_url')
    op.drop_column('companies', 'domain')
