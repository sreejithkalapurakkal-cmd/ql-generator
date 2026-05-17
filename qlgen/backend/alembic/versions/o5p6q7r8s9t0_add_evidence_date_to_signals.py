"""add evidence_date to signal_events

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-05-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add evidence_date column — the date the real-world event occurred,
    # as opposed to detected_at which is when qlGen discovered it.
    op.add_column(
        "signal_events",
        sa.Column("evidence_date", sa.DateTime(timezone=True), nullable=True),
    )
    # Index for sorting signals by evidence freshness
    op.create_index(
        "ix_signal_evidence_date",
        "signal_events",
        ["evidence_date"],
    )
    # Backfill: set evidence_date = detected_at for existing rows
    op.execute("UPDATE signal_events SET evidence_date = detected_at WHERE evidence_date IS NULL")


def downgrade() -> None:
    op.drop_index("ix_signal_evidence_date", table_name="signal_events")
    op.drop_column("signal_events", "evidence_date")
