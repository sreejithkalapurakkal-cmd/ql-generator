"""add signal save/snooze lifecycle columns

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-05-17 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("signal_events", sa.Column("is_saved", sa.Boolean(), server_default="false"))
    op.add_column("signal_events", sa.Column("is_snoozed", sa.Boolean(), server_default="false"))
    op.add_column("signal_events", sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("signal_events", sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("signal_events", sa.Column("snoozed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_signal_saved", "signal_events", ["is_saved"])
    op.create_index("ix_signal_snoozed", "signal_events", ["is_snoozed", "snoozed_until"])


def downgrade() -> None:
    op.drop_index("ix_signal_snoozed", table_name="signal_events")
    op.drop_index("ix_signal_saved", table_name="signal_events")
    op.drop_column("signal_events", "snoozed_at")
    op.drop_column("signal_events", "saved_at")
    op.drop_column("signal_events", "snoozed_until")
    op.drop_column("signal_events", "is_snoozed")
    op.drop_column("signal_events", "is_saved")
