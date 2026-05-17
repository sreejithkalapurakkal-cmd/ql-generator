"""add dismissed_at, signal_detection_logs, enrichment_runs, enrichment_logs

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-05-14 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dismissed_at to ingest_batches
    op.add_column(
        "ingest_batches",
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Create signal_detection_logs table
    op.create_table(
        "signal_detection_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "signal_detection_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("signal_detection_runs.id", ondelete="CASCADE"),
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
        "ix_sigdet_log_run_seq",
        "signal_detection_logs",
        ["signal_detection_run_id", "sequence_number"],
    )

    # 3. Create enrichment_runs table
    op.create_table(
        "enrichment_runs",
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
        sa.Column("contacts_found", sa.Integer, server_default="0"),
        sa.Column("target_roles", JSONB, nullable=True),
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
        "ix_enrichrun_list_created",
        "enrichment_runs",
        ["tracking_list_id", "created_at"],
    )
    op.create_index("ix_enrichrun_user", "enrichment_runs", ["user_id"])

    # 4. Create enrichment_logs table
    op.create_table(
        "enrichment_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "enrichment_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("enrichment_runs.id", ondelete="CASCADE"),
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
        "ix_enrich_log_run_seq",
        "enrichment_logs",
        ["enrichment_run_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_table("enrichment_logs")
    op.drop_table("enrichment_runs")
    op.drop_table("signal_detection_logs")
    op.drop_column("ingest_batches", "dismissed_at")
