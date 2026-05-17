"""add verbosity_level to activity_events, signal_hypotheses to ingest_batches

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-05-17 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("activity_events", sa.Column("verbosity_level", sa.String(20), server_default="summary"))
    op.add_column("ingest_batches", sa.Column("signal_hypotheses", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("ingest_batches", "signal_hypotheses")
    op.drop_column("activity_events", "verbosity_level")
