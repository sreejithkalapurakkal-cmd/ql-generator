import uuid
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class TrackingList(Base):
    """Named, user-owned collection of tracked companies.

    Companies are tracked via TrackingListMembership, which references
    CompanyKnowledgeBase (golden records) — not per-run Company records.
    """
    __tablename__ = "tracking_lists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Signal monitoring configuration
    # Schema: {enabled: bool, frequency_days: int, signal_types: [...], alert_threshold: str}
    monitoring_config = Column(JSONB, default=dict)
    last_monitored_at = Column(DateTime(timezone=True))
    next_monitor_due = Column(DateTime(timezone=True))

    # User-provided signal research hints
    # Schema: {budget_signals: str[], urgency_signals: str[], custom_hints: str[], target_roles: str[]}
    signal_hints = Column(JSONB, default=dict)

    # Denormalized for fast list display
    company_count = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", lazy="selectin")
    memberships = relationship(
        "TrackingListMembership",
        back_populates="tracking_list",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
