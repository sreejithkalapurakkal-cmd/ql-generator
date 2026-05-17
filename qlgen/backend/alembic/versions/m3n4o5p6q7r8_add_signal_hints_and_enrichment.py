"""add signal hints and enrichment status

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-04 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add signal_hints JSONB to tracking_lists
    op.add_column(
        "tracking_lists",
        sa.Column("signal_hints", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
    )

    # Add enrichment_status to tracking_list_memberships
    op.add_column(
        "tracking_list_memberships",
        sa.Column("enrichment_status", sa.String(50), server_default="not_started", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracking_list_memberships", "enrichment_status")
    op.drop_column("tracking_lists", "signal_hints")
