"""add brief_revisions, drafts, and activity_events tables

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-05-17 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── brief_revisions ──────────────────────────────────────────────────
    op.create_table(
        "brief_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_kb_id", UUID(as_uuid=True), sa.ForeignKey("company_knowledge_base.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sections", JSONB, nullable=False),
        sa.Column("word_count", sa.Integer()),
        sa.Column("generated_by", sa.String(20), server_default="auto"),
        sa.Column("trigger_signal_id", UUID(as_uuid=True), sa.ForeignKey("signal_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trigger_signal_headline", sa.String(500)),
        sa.Column("model_id", sa.String(100)),
        sa.Column("generation_cost_usd", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_brief_company", "brief_revisions", ["company_kb_id", "version"])
    op.create_unique_constraint("uq_brief_company_version", "brief_revisions", ["company_kb_id", "version"])

    # ── drafts ───────────────────────────────────────────────────────────
    op.create_table(
        "drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_kb_id", UUID(as_uuid=True), sa.ForeignKey("company_knowledge_base.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", UUID(as_uuid=True), sa.ForeignKey("signal_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_name", sa.String(500)),
        sa.Column("contact_title", sa.String(500)),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("tone", sa.String(20), server_default="direct"),
        sa.Column("voice_profile", sa.String(20), server_default="concise"),
        sa.Column("subject", sa.String(500)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("hooks_used", JSONB, server_default="[]"),
        sa.Column("status", sa.String(20), server_default="in_progress"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_draft_company", "drafts", ["company_kb_id", "created_at"])
    op.create_index("ix_draft_status", "drafts", ["status"])

    # ── activity_events ──────────────────────────────────────────────────
    op.create_table(
        "activity_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("research_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("company_kb_id", UUID(as_uuid=True), sa.ForeignKey("company_knowledge_base.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_category", sa.String(50)),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("narrative_detail", sa.Text()),
        sa.Column("technical_detail", JSONB),
        sa.Column("confidence", sa.Float()),
        sa.Column("milestone", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_job", "activity_events", ["research_job_id", "created_at"])
    op.create_index("ix_activity_company", "activity_events", ["company_kb_id", "created_at"])

    # ── Add has_brief and open_draft_count to company_knowledge_base ────
    op.add_column("company_knowledge_base", sa.Column("has_brief", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("company_knowledge_base", sa.Column("open_draft_count", sa.Integer(), server_default=sa.text("0")))
    op.add_column("company_knowledge_base", sa.Column("latest_brief_version", sa.Integer()))


def downgrade() -> None:
    op.drop_column("company_knowledge_base", "latest_brief_version")
    op.drop_column("company_knowledge_base", "open_draft_count")
    op.drop_column("company_knowledge_base", "has_brief")
    op.drop_index("ix_activity_company", table_name="activity_events")
    op.drop_index("ix_activity_job", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_index("ix_draft_status", table_name="drafts")
    op.drop_index("ix_draft_company", table_name="drafts")
    op.drop_table("drafts")
    op.drop_constraint("uq_brief_company_version", "brief_revisions", type_="unique")
    op.drop_index("ix_brief_company", table_name="brief_revisions")
    op.drop_table("brief_revisions")
