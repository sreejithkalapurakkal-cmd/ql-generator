import uuid
from sqlalchemy import Column, String, Text, Integer, BigInteger, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class CompanyKnowledgeBase(Base):
    """Canonical 'golden record' per unique company domain.

    Merges the richest data from all pipeline runs into a single row,
    keyed by normalized domain.
    """
    __tablename__ = "company_knowledge_base"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    normalized_domain = Column(String(500), unique=True, nullable=False, index=True)
    canonical_name = Column(String(500))

    # Firmographics
    industry = Column(String(255))
    sub_industry = Column(String(255))
    country = Column(String(255))
    city = Column(String(255))
    state_region = Column(String(255))
    employee_count = Column(Integer)
    revenue_estimate = Column(BigInteger)
    asset_value = Column(BigInteger)

    # Tech / Description
    tech_stack_json = Column(JSONB)
    description = Column(Text)

    # Best-ever scores
    best_icp_match_score = Column(Float)
    best_budget_signal_score = Column(Float)
    best_urgency_signal_score = Column(Float)
    best_final_score = Column(Float)
    best_deal_hotness_score = Column(Float)
    best_deal_hotness_tier = Column(String(20))

    # Contacts (top 10 by confidence, deduplicated)
    best_known_contacts = Column(JSONB)

    # Per-field provenance tracking
    data_sources = Column(JSONB)

    # Embedding (1024-dim, same as Company model)
    embedding = Column(Vector(1024), nullable=True)

    # Metadata
    times_discovered = Column(Integer, default=1)
    pipeline_run_ids = Column(JSONB)  # list of UUID strings
    first_discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_enriched_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_kb_industry", "industry"),
        Index("ix_kb_country", "country"),
        Index("ix_kb_best_final_score", "best_final_score"),
        Index(
            "ix_kb_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
