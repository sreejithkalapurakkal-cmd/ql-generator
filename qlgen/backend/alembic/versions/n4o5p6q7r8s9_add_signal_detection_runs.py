"""add signal detection runs table

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_detection_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tracking_list_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tracking_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("total_companies", sa.Integer, server_default="0"),
        sa.Column("processed_companies", sa.Integer, server_default="0"),
        sa.Column("signals_detected", sa.Integer, server_default="0"),
        sa.Column("use_agent", sa.Boolean, server_default="false"),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_sigdetrun_list_created",
        "signal_detection_runs",
        ["tracking_list_id", "created_at"],
    )
    op.create_index(
        "ix_sigdetrun_user",
        "signal_detection_runs",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sigdetrun_user", table_name="signal_detection_runs")
    op.drop_index("ix_sigdetrun_list_created", table_name="signal_detection_runs")
    op.drop_table("signal_detection_runs")
