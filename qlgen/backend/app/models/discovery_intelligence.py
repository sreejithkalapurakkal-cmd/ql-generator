"""Cross-run discovery intelligence model.

Records which search queries and tools produced high-scoring companies,
enabling the system to learn from past runs and prioritize effective
strategies for similar ICPs.
"""

import uuid
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base


class DiscoveryQuery(Base):
    """Records a search query that discovered companies in a pipeline run."""
    __tablename__ = "discovery_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_run_id = Column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id"))
    icp_config_id = Column(UUID(as_uuid=True), ForeignKey("icp_configs.id"))

    # What query/tool was used
    tool_name = Column(String(100), nullable=False)
    query_text = Column(Text)  # The actual search query or tool parameters

    # ICP context for matching similar future ICPs
    industry = Column(String(255))
    country = Column(String(255))

    # Results metrics
    companies_found = Column(Integer, default=0)
    companies_passed_stage2 = Column(Integer, default=0)  # How many passed firmographic fit
    avg_final_score = Column(Float)  # Average final score of companies from this query

    # Effectiveness score (computed): passed_stage2 / companies_found * avg_final_score
    effectiveness_score = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ToolEffectiveness(Base):
    """Tracks aggregate tool effectiveness across pipeline runs."""
    __tablename__ = "tool_effectiveness"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tool_name = Column(String(100), nullable=False)
    industry = Column(String(255))  # Industry context
    country = Column(String(255))   # Country context

    # Aggregate metrics
    total_companies_sourced = Column(Integer, default=0)
    companies_passed_stage2 = Column(Integer, default=0)
    avg_final_score = Column(Float, default=0.0)
    total_runs_used = Column(Integer, default=0)

    # Computed effectiveness: (passed / total) * avg_score
    effectiveness_score = Column(Float, default=0.0)

    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
