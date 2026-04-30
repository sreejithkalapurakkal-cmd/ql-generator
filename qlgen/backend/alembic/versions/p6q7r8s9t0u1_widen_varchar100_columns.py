"""widen varchar(100) columns to varchar(500) to prevent truncation errors

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-04-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'p6q7r8s9t0u1'
down_revision: Union[str, None] = 'o5p6q7r8s9t0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # contacts table
    op.alter_column('contacts', 'source', type_=sa.String(500), existing_type=sa.String(100))
    op.alter_column('contacts', 'role_category', type_=sa.String(500), existing_type=sa.String(100))
    op.alter_column('contacts', 'phone', type_=sa.String(500), existing_type=sa.String(100))

    # companies table
    op.alter_column('companies', 'source', type_=sa.String(500), existing_type=sa.String(100))
    op.alter_column('companies', 'company_type', type_=sa.String(500), existing_type=sa.String(100))
    op.alter_column('companies', 'funding_stage', type_=sa.String(500), existing_type=sa.String(100))

    # company_knowledge_base table
    op.alter_column('company_knowledge_base', 'company_type', type_=sa.String(500), existing_type=sa.String(100))
    op.alter_column('company_knowledge_base', 'funding_stage', type_=sa.String(500), existing_type=sa.String(100))


def downgrade() -> None:
    op.alter_column('company_knowledge_base', 'funding_stage', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('company_knowledge_base', 'company_type', type_=sa.String(100), existing_type=sa.String(500))

    op.alter_column('companies', 'funding_stage', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('companies', 'company_type', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('companies', 'source', type_=sa.String(100), existing_type=sa.String(500))

    op.alter_column('contacts', 'phone', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('contacts', 'role_category', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('contacts', 'source', type_=sa.String(100), existing_type=sa.String(500))
