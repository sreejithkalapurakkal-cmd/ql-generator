"""add research_jobs, custom_signal_sources, source_snapshots tables + enhanced signal/KB fields

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-05-17 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Research Jobs
    op.create_table(
        "research_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_kb_id", UUID(as_uuid=True), sa.ForeignKey("company_knowledge_base.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("research_depth", sa.String(20), server_default="standard"),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("plan", JSONB, nullable=True),
        sa.Column("progress", JSONB, server_default="{}"),
        sa.Column("current_stage", sa.String(100), nullable=True),
        sa.Column("results", JSONB, nullable=True),
        sa.Column("signals_detected", sa.Integer(), server_default="0"),
        sa.Column("contacts_found", sa.Integer(), server_default="0"),
        sa.Column("brief_version", sa.Integer(), nullable=True),
        sa.Column("total_tool_calls", sa.Integer(), server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_research_job_company", "research_jobs", ["company_kb_id", "created_at"])
    op.create_index("ix_research_job_status", "research_jobs", ["status"])
    op.create_index("ix_research_job_user", "research_jobs", ["user_id"])

    # Custom Signal Sources
    op.create_table(
        "custom_signal_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_kb_id", UUID(as_uuid=True), sa.ForeignKey("company_knowledge_base.id", ondelete="CASCADE"), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("crawl_frequency", sa.String(20), server_default="weekly"),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_content_hash", sa.String(64), nullable=True),
        sa.Column("reliability_score", sa.Float(), server_default="0.5"),
        sa.Column("freshness_score", sa.Float(), server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("crawl_config", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_source_user", "custom_signal_sources", ["user_id"])
    op.create_index("ix_source_company", "custom_signal_sources", ["company_kb_id"])

    # Source Snapshots
    op.create_table(
        "source_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("custom_signal_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("extracted_signals", JSONB, server_default="[]"),
        sa.Column("crawled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_snapshot_source", "source_snapshots", ["source_id", "crawled_at"])

    # Enhanced SignalEvent fields
    op.add_column("signal_events", sa.Column("confidence", sa.String(20), nullable=True))
    op.add_column("signal_events", sa.Column("source_class", sa.String(100), nullable=True))
    op.add_column("signal_events", sa.Column("headline", sa.String(500), nullable=True))
    op.add_column("signal_events", sa.Column("region", sa.String(100), nullable=True))
    op.add_column("signal_events", sa.Column("research_job_id", UUID(as_uuid=True), nullable=True))
    op.add_column("signal_events", sa.Column("custom_rule_id", UUID(as_uuid=True), nullable=True))

    # Enhanced CompanyKnowledgeBase fields
    op.add_column("company_knowledge_base", sa.Column("status", sa.String(20), server_default="monitored"))
    op.add_column("company_knowledge_base", sa.Column("owner", sa.String(255), nullable=True))
    op.add_column("company_knowledge_base", sa.Column("signal_count", sa.Integer(), server_default="0"))
    op.add_column("company_knowledge_base", sa.Column("tags", JSONB, server_default="[]"))


def downgrade() -> None:
    op.drop_column("company_knowledge_base", "tags")
    op.drop_column("company_knowledge_base", "signal_count")
    op.drop_column("company_knowledge_base", "owner")
    op.drop_column("company_knowledge_base", "status")
    op.drop_column("signal_events", "custom_rule_id")
    op.drop_column("signal_events", "research_job_id")
    op.drop_column("signal_events", "region")
    op.drop_column("signal_events", "headline")
    op.drop_column("signal_events", "source_class")
    op.drop_column("signal_events", "confidence")
    op.drop_index("ix_snapshot_source", table_name="source_snapshots")
    op.drop_table("source_snapshots")
    op.drop_index("ix_source_company", table_name="custom_signal_sources")
    op.drop_index("ix_source_user", table_name="custom_signal_sources")
    op.drop_table("custom_signal_sources")
    op.drop_index("ix_research_job_user", table_name="research_jobs")
    op.drop_index("ix_research_job_status", table_name="research_jobs")
    op.drop_index("ix_research_job_company", table_name="research_jobs")
    op.drop_table("research_jobs")
