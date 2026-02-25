import uuid
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
    full_name = Column(String(500))
    first_name = Column(String(255))
    last_name = Column(String(255))
    designation = Column(String(500))
    role_category = Column(String(100))
    email = Column(String(500))
    phone = Column(String(100))
    linkedin_url = Column(String(500))
    city = Column(String(255))
    source = Column(String(100))
    confidence = Column(Float)
    enrichment_status = Column(String(50), default="pending")
    raw_data_json = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="contacts")
