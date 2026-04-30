"""add feedback and feedback_replies tables

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-04-06

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'l2m3n4o5p6q7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS to handle the case where tables were
    # created in a previous partial deployment but alembic_version wasn't stamped.
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            type VARCHAR(30) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_feedback_user_id ON feedback (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_feedback_type ON feedback (type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_feedback_status ON feedback (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_feedback_user_status ON feedback (user_id, status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback_replies (
            id UUID PRIMARY KEY,
            feedback_id UUID NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_feedback_replies_feedback_id ON feedback_replies (feedback_id)")


def downgrade() -> None:
    op.drop_table('feedback_replies')
    op.drop_table('feedback')
