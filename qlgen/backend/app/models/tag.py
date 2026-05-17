import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base


class Tag(Base):
    """User-created label for categorizing tracking list members.

    Tags are applied as a JSONB array of tag UUIDs on
    TrackingListMembership.tags (GIN indexed). The Tag model defines
    available tags (name + color) per user.
    """
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#5C2D8F")  # hex color, matches qlGen primary

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
    )
