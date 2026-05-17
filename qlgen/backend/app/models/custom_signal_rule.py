import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class CustomSignalRule(Base):
    """User-defined signal detection rule.

    Rules can be scoped to a tracking list or global (user-wide).
    When signal detection runs, custom rules are evaluated against
    research data to generate additional signals.

    Rule types:
      - keyword: Match keywords in search results
      - pattern: Regex / structured pattern matching
      - composite: Multi-signal correlation (e.g., funding + hiring = critical)

    rule_config schema varies by type:
      keyword: {keywords: str[], match_any: bool, source_types: str[]}
      pattern: {pattern: str, source_types: str[], field: str}
      composite: {conditions: [{signal_type: str, min_count: int, within_days: int}], operator: "all"|"any"}
    """
    __tablename__ = "custom_signal_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tracking_list_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tracking_lists.id", ondelete="CASCADE"),
        nullable=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Rule definition
    rule_type = Column(String(30), nullable=False)  # keyword, pattern, composite
    rule_config = Column(JSONB, nullable=False, default=dict)

    # Output signal properties when rule fires
    signal_type_output = Column(String(50), default="custom_signal")
    priority_output = Column(String(20), default="medium")

    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True))
    trigger_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_custom_rule_user", "user_id"),
        Index("ix_custom_rule_list", "tracking_list_id"),
        Index("ix_custom_rule_active", "is_active"),
    )
