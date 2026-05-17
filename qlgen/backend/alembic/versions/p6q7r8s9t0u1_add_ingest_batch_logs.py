"""add ingest_batch_logs table

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-05-13 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_batch_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingest_batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ingest_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_ingest_batch_log_batch_seq",
        "ingest_batch_logs",
        ["ingest_batch_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_batch_log_batch_seq", table_name="ingest_batch_logs")
    op.drop_table("ingest_batch_logs")
