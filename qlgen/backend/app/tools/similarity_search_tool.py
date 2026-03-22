"""Pipeline tool: find similar companies from past runs using pgvector embeddings.

Uses the existing Company embeddings (1024-dim Titan Embed Text v2) to find
semantically similar companies from previous pipeline runs. Helps the Stage 1
agent expand discovery by finding companies the keyword searches missed.
"""

import logging

from strands import tool

logger = logging.getLogger(__name__)


@tool
def find_similar_companies(
    company_name: str,
    description: str = "",
    limit: int = 20,
) -> dict:
    """
    Find companies similar to a given company using semantic embedding similarity.
    Searches across ALL previous pipeline runs (not the current one).
    BEST FOR: Expanding discovery after finding a good match — finds companies
    that keyword searches miss by using semantic similarity.
    USE IN STAGE: Company Discovery (Stage 1)

    Args:
        company_name: Name of the reference company to find similar ones to
        description: Optional description of the company for better matching.
            More text = better semantic matching. Include industry, products, location.
        limit: Maximum number of similar companies to return (default 20, max 50)

    Returns:
        dict with 'similar_companies' list containing name, website, industry,
        employee_count, country, similarity_score from past pipeline runs
    """
    from app.services.embedding_service import generate_embedding
    from app.db.session import sync_engine
    from sqlalchemy import text as sa_text

    limit = min(limit, 50)

    # Build search text from company name + description
    search_text = f"{company_name}. {description}" if description else company_name
    search_text = search_text[:8000]  # Truncate to embedding model limit

    try:
        embedding = generate_embedding(search_text)
        if not embedding:
            return {
                "similar_companies": [],
                "error": "Could not generate embedding for the search text",
            }

        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Use sync engine since Strands tools run synchronously
        from sqlalchemy import create_engine
        from app.config import get_settings
        settings = get_settings()

        # Build sync connection string from async one
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

        from sqlalchemy import create_engine as _ce
        engine = _ce(sync_url, pool_pre_ping=True)

        with engine.connect() as conn:
            result = conn.execute(
                sa_text("""
                    SELECT c.name, c.website, c.industry, c.sub_industry,
                           c.city, c.state_region, c.country,
                           c.employee_count, c.revenue_estimate,
                           c.description,
                           1 - (c.embedding <=> :embedding::vector) as similarity
                    FROM companies c
                    WHERE c.embedding IS NOT NULL
                      AND 1 - (c.embedding <=> :embedding::vector) > 0.5
                    ORDER BY c.embedding <=> :embedding::vector
                    LIMIT :limit
                """),
                {
                    "embedding": embedding_str,
                    "limit": limit,
                },
            )
            rows = result.fetchall()

        similar = []
        for row in rows:
            similar.append({
                "name": row.name,
                "website": row.website or "",
                "industry": row.industry or "",
                "sub_industry": row.sub_industry or "",
                "country": row.country or "",
                "city": row.city or "",
                "employee_count": row.employee_count,
                "revenue_estimate": row.revenue_estimate,
                "description": (row.description or "")[:200],
                "similarity_score": round(float(row.similarity), 3),
            })

        logger.info(
            f"find_similar_companies: found {len(similar)} matches "
            f"for '{company_name}' (threshold 0.5)"
        )

        return {
            "similar_companies": similar,
            "query": company_name,
            "total_found": len(similar),
        }

    except Exception as e:
        logger.warning(f"find_similar_companies failed: {e}")
        return {
            "similar_companies": [],
            "error": str(e),
        }
