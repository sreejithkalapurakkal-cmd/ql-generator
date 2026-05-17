"""add custom_signal_rules table

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-05-17 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, None] = "s9t0u1v2w3x4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_signal_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tracking_list_id", UUID(as_uuid=True), sa.ForeignKey("tracking_lists.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("rule_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("signal_type_output", sa.String(50), server_default="custom_signal"),
        sa.Column("priority_output", sa.String(20), server_default="medium"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_custom_rule_user", "custom_signal_rules", ["user_id"])
    op.create_index("ix_custom_rule_list", "custom_signal_rules", ["tracking_list_id"])
    op.create_index("ix_custom_rule_active", "custom_signal_rules", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_custom_rule_active", table_name="custom_signal_rules")
    op.drop_index("ix_custom_rule_list", table_name="custom_signal_rules")
    op.drop_index("ix_custom_rule_user", table_name="custom_signal_rules")
    op.drop_table("custom_signal_rules")
