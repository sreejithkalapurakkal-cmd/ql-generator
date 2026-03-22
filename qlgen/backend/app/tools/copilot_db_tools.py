"""Database search tools for the co-pilot agent.

These tools use a synchronous SQLAlchemy engine because the Strands agent runs
in a thread pool executor (same pattern as the lead gen agent).
"""
import json
import logging
from uuid import UUID

from sqlalchemy import create_engine, select, func, text, and_, or_, cast, String
from sqlalchemy.orm import sessionmaker, joinedload
from strands import tool

from app.config import get_settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.company_stage import CompanyStageResult
from app.models.icp import ICPConfig
from app.models.pipeline import PipelineRun
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services.embedding_service import generate_embedding
from app.auth.context import current_user_id, current_user_is_admin

logger = logging.getLogger(__name__)
settings = get_settings()

_sync_engine = None
_SyncSession = None


def _get_sync_session():
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
        _SyncSession = sessionmaker(bind=_sync_engine)
    return _SyncSession()


def _get_user_scope():
    """Return (user_id, is_admin) from context vars."""
    uid = current_user_id.get()
    admin = current_user_is_admin.get()
    return uid, admin


def _apply_company_user_filter(query, session_obj=None):
    """Add a JOIN to pipeline_runs and filter by user_id for non-admin users.

    Works with ORM-style queries (session.query(Company)...).
    """
    uid, admin = _get_user_scope()
    if admin or uid is None:
        return query
    query = query.join(PipelineRun, Company.pipeline_run_id == PipelineRun.id)
    query = query.filter(PipelineRun.user_id == uid)
    return query


def _company_to_dict(company, include_contacts=False):
    """Serialize a Company ORM object to a dict."""
    result = {
        "id": str(company.id),
        "name": company.name,
        "website": company.website,
        "industry": company.industry,
        "sub_industry": company.sub_industry,
        "city": company.city,
        "state_region": company.state_region,
        "country": company.country,
        "employee_count": company.employee_count,
        "revenue_estimate": company.revenue_estimate,
        "tech_stack": company.tech_stack_json,
        "source": company.source,
        "icp_match_score": company.icp_match_score,
        "match_reasoning": company.match_reasoning,
        "qualification": company.qualification,
        "current_stage": company.current_stage,
        "budget_signal_score": company.budget_signal_score,
        "urgency_signal_score": company.urgency_signal_score,
        "final_score": company.final_score,
        "final_rank": company.final_rank,
    }

    if include_contacts and company.contacts:
        result["contacts"] = [
            {
                "id": str(c.id),
                "full_name": c.full_name,
                "designation": c.designation,
                "role_category": c.role_category,
                "email": c.email,
                "phone": c.phone,
                "linkedin_url": c.linkedin_url,
                "source": c.source,
                "confidence": c.confidence,
            }
            for c in company.contacts
        ]

    return result


@tool
def search_companies_semantic(query: str, limit: int = 10) -> str:
    """
    Search companies using semantic similarity (vector search).
    Finds companies whose profiles are semantically similar to the query.
    BEST FOR: Natural language queries like "fintech companies in Europe"
    or "companies with legacy tech stack needing modernization".

    Args:
        query: Natural language search query describing what you're looking for
        limit: Maximum number of results to return (default 10, max 25)

    Returns:
        JSON string with matching companies and similarity scores
    """
    limit = min(limit, 25)
    embedding = generate_embedding(query)
    if not embedding is None:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    else:
        return json.dumps({"error": "Failed to generate embedding for query", "companies": []})

    uid, admin = _get_user_scope()

    session = _get_sync_session()
    try:
        # Build user-scoped SQL
        user_join = ""
        user_where = ""
        params = {"embedding": embedding_str, "limit": limit}
        if not admin and uid is not None:
            user_join = "JOIN pipeline_runs pr ON c.pipeline_run_id = pr.id"
            user_where = "AND pr.user_id = :user_id"
            params["user_id"] = str(uid)

        results = session.execute(
            text(f"""
                SELECT c.id, c.name, c.website, c.industry, c.sub_industry,
                       c.city, c.state_region, c.country, c.employee_count,
                       c.revenue_estimate, c.tech_stack_json, c.source,
                       c.icp_match_score, c.match_reasoning, c.qualification,
                       c.final_score, c.current_stage,
                       1 - (c.embedding <=> :embedding::vector) as similarity
                FROM companies c
                {user_join}
                WHERE c.embedding IS NOT NULL {user_where}
                ORDER BY c.embedding <=> :embedding::vector
                LIMIT :limit
            """),
            params,
        )

        companies = []
        for row in results:
            companies.append({
                "id": str(row.id),
                "name": row.name,
                "website": row.website,
                "industry": row.industry,
                "sub_industry": row.sub_industry,
                "city": row.city,
                "state_region": row.state_region,
                "country": row.country,
                "employee_count": row.employee_count,
                "revenue_estimate": row.revenue_estimate,
                "tech_stack": row.tech_stack_json,
                "source": row.source,
                "icp_match_score": row.icp_match_score,
                "match_reasoning": row.match_reasoning,
                "qualification": row.qualification,
                "final_score": row.final_score,
                "current_stage": row.current_stage,
                "similarity": round(row.similarity, 4) if row.similarity else None,
            })

        return json.dumps({
            "query": query,
            "count": len(companies),
            "companies": companies,
        })
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return json.dumps({"error": str(e), "companies": []})
    finally:
        session.close()


@tool
def search_companies_structured(
    industry: str = None,
    country: str = None,
    city: str = None,
    min_final_score: float = None,
    max_final_score: float = None,
    min_employees: int = None,
    max_employees: int = None,
    tech_keyword: str = None,
    limit: int = 20,
) -> str:
    """
    Search companies using structured filters on known fields.
    BEST FOR: Precise filtering by industry, location, score range, size.

    Args:
        industry: Filter by industry name (partial match, case-insensitive)
        country: Filter by country (partial match)
        city: Filter by city (partial match)
        min_final_score: Minimum final score (0-100)
        max_final_score: Maximum final score (0-100)
        min_employees: Minimum employee count
        max_employees: Maximum employee count
        tech_keyword: Search for a keyword in tech stack JSON
        limit: Maximum results (default 20, max 50)

    Returns:
        JSON string with matching companies
    """
    limit = min(limit, 50)
    session = _get_sync_session()
    try:
        query = (
            session.query(Company)
            .options(
                joinedload(Company.contacts),
            )
        )

        # Apply user scoping
        query = _apply_company_user_filter(query)

        if industry:
            query = query.filter(Company.industry.ilike(f"%{industry}%"))
        if country:
            query = query.filter(Company.country.ilike(f"%{country}%"))
        if city:
            query = query.filter(Company.city.ilike(f"%{city}%"))
        if min_employees is not None:
            query = query.filter(Company.employee_count >= min_employees)
        if max_employees is not None:
            query = query.filter(Company.employee_count <= max_employees)
        if min_final_score is not None:
            query = query.filter(Company.final_score >= min_final_score)
        if max_final_score is not None:
            query = query.filter(Company.final_score <= max_final_score)
        if tech_keyword:
            query = query.filter(
                cast(Company.tech_stack_json, String).ilike(f"%{tech_keyword}%")
            )

        query = query.order_by(Company.final_score.desc().nullslast())
        companies = query.limit(limit).all()

        results = [_company_to_dict(c, include_contacts=True) for c in companies]
        return json.dumps({
            "count": len(results),
            "filters_applied": {
                k: v for k, v in {
                    "industry": industry, "country": country, "city": city,
                    "min_final_score": min_final_score, "max_final_score": max_final_score,
                    "min_employees": min_employees, "max_employees": max_employees,
                    "tech_keyword": tech_keyword,
                }.items() if v is not None
            },
            "companies": results,
        })
    except Exception as e:
        logger.error(f"Structured search failed: {e}")
        return json.dumps({"error": str(e), "companies": []})
    finally:
        session.close()


@tool
def get_company_details(company_id: str) -> str:
    """
    Get full details for a specific company by its UUID.
    Returns all company data, contacts, and stage results.

    Args:
        company_id: The UUID of the company

    Returns:
        JSON string with full company details including contacts and stage results
    """
    uid, admin = _get_user_scope()
    session = _get_sync_session()
    try:
        query = (
            session.query(Company)
            .options(
                joinedload(Company.contacts),
                joinedload(Company.stage_results),
            )
            .filter(Company.id == company_id)
        )

        # Verify company belongs to user via pipeline_run
        if not admin and uid is not None:
            query = query.join(PipelineRun, Company.pipeline_run_id == PipelineRun.id).filter(
                PipelineRun.user_id == uid
            )

        company = query.first()

        if not company:
            return json.dumps({"error": f"Company {company_id} not found"})

        result = _company_to_dict(company, include_contacts=True)

        # Add stage results
        if company.stage_results:
            result["stage_results"] = [
                {
                    "stage": sr.stage,
                    "status": sr.status,
                    "score": sr.score,
                    "reasoning": sr.reasoning,
                    "evidence": sr.evidence,
                    "user_override": sr.user_override,
                }
                for sr in company.stage_results
            ]

        return json.dumps(result)
    except Exception as e:
        logger.error(f"Get company details failed: {e}")
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@tool
def get_icp_details(icp_id: str = None) -> str:
    """
    Get ICP configuration details. If icp_id is provided, returns that specific ICP.
    Otherwise returns all active ICPs.

    Args:
        icp_id: Optional UUID of a specific ICP to retrieve

    Returns:
        JSON string with ICP configuration(s)
    """
    uid, admin = _get_user_scope()
    session = _get_sync_session()
    try:
        if icp_id:
            query = session.query(ICPConfig).filter(ICPConfig.id == icp_id)
            if not admin and uid is not None:
                query = query.filter(ICPConfig.user_id == uid)
            icp = query.first()
            if not icp:
                return json.dumps({"error": f"ICP {icp_id} not found"})
            return json.dumps({
                "id": str(icp.id),
                "name": icp.name,
                "description": icp.description,
                "config": icp.config_json,
                "created_at": str(icp.created_at) if icp.created_at else None,
                "is_active": icp.is_active,
            })

        query = (
            session.query(ICPConfig)
            .filter(ICPConfig.is_active == True)
        )
        if not admin and uid is not None:
            query = query.filter(ICPConfig.user_id == uid)
        icps = query.order_by(ICPConfig.created_at.desc()).all()

        return json.dumps({
            "count": len(icps),
            "icps": [
                {
                    "id": str(i.id),
                    "name": i.name,
                    "description": i.description,
                    "config": i.config_json,
                    "created_at": str(i.created_at) if i.created_at else None,
                }
                for i in icps
            ],
        })
    except Exception as e:
        logger.error(f"Get ICP details failed: {e}")
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@tool
def get_pipeline_summary(run_id: str = None) -> str:
    """
    Get pipeline run summary. If run_id is provided, returns that specific run.
    Otherwise returns all runs with their stats.

    Args:
        run_id: Optional UUID of a specific pipeline run

    Returns:
        JSON string with pipeline run summary/stats
    """
    uid, admin = _get_user_scope()
    session = _get_sync_session()
    try:
        if run_id:
            query = session.query(PipelineRun).filter(PipelineRun.id == run_id)
            if not admin and uid is not None:
                query = query.filter(PipelineRun.user_id == uid)
            run = query.first()
            if not run:
                return json.dumps({"error": f"Pipeline run {run_id} not found"})

            # Get associated ICP name
            icp = session.query(ICPConfig).filter(ICPConfig.id == run.icp_config_id).first()

            return json.dumps({
                "id": str(run.id),
                "icp_name": icp.name if icp else None,
                "status": run.status,
                "current_stage": run.current_stage,
                "signal_mode": run.signal_mode,
                "signal_phase": run.signal_phase,
                "companies_found": run.companies_found,
                "contacts_found": run.contacts_found,
                "started_at": str(run.started_at) if run.started_at else None,
                "completed_at": str(run.completed_at) if run.completed_at else None,
            })

        query = session.query(PipelineRun)
        if not admin and uid is not None:
            query = query.filter(PipelineRun.user_id == uid)
        runs = (
            query
            .order_by(PipelineRun.started_at.desc().nullslast())
            .limit(20)
            .all()
        )

        results = []
        for run in runs:
            icp = session.query(ICPConfig).filter(ICPConfig.id == run.icp_config_id).first()
            results.append({
                "id": str(run.id),
                "icp_name": icp.name if icp else None,
                "status": run.status,
                "signal_mode": run.signal_mode,
                "companies_found": run.companies_found,
                "contacts_found": run.contacts_found,
                "started_at": str(run.started_at) if run.started_at else None,
                "completed_at": str(run.completed_at) if run.completed_at else None,
            })

        return json.dumps({"count": len(results), "runs": results})
    except Exception as e:
        logger.error(f"Get pipeline summary failed: {e}")
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@tool
def get_data_statistics() -> str:
    """
    Get aggregate statistics across all data: totals, industry breakdown,
    score distribution, geographic distribution, and more.

    Returns:
        JSON string with comprehensive data statistics
    """
    uid, admin = _get_user_scope()
    session = _get_sync_session()
    try:
        # Build base company query with user scoping
        def scoped_company_query():
            q = session.query(Company)
            if not admin and uid is not None:
                q = q.join(PipelineRun, Company.pipeline_run_id == PipelineRun.id).filter(
                    PipelineRun.user_id == uid
                )
            return q

        # Totals
        total_companies = scoped_company_query().with_entities(func.count(Company.id)).scalar() or 0

        # Contact count (scoped through companies)
        contact_q = session.query(func.count(Contact.id)).join(Company, Contact.company_id == Company.id)
        if not admin and uid is not None:
            contact_q = contact_q.join(PipelineRun, Company.pipeline_run_id == PipelineRun.id).filter(
                PipelineRun.user_id == uid
            )
        total_contacts = contact_q.scalar() or 0

        # Pipeline run count
        run_q = session.query(func.count(PipelineRun.id))
        if not admin and uid is not None:
            run_q = run_q.filter(PipelineRun.user_id == uid)
        total_runs = run_q.scalar() or 0

        # ICP count
        icp_q = session.query(func.count(ICPConfig.id)).filter(ICPConfig.is_active == True)
        if not admin and uid is not None:
            icp_q = icp_q.filter(ICPConfig.user_id == uid)
        total_icps = icp_q.scalar() or 0

        # Score distribution
        avg_final = scoped_company_query().with_entities(
            func.avg(Company.final_score)
        ).filter(Company.final_score.isnot(None)).scalar()

        high_score = scoped_company_query().with_entities(
            func.count(Company.id)
        ).filter(Company.final_score >= 75).scalar() or 0

        medium_score = scoped_company_query().with_entities(
            func.count(Company.id)
        ).filter(Company.final_score >= 50, Company.final_score < 75).scalar() or 0

        low_score = scoped_company_query().with_entities(
            func.count(Company.id)
        ).filter(Company.final_score > 0, Company.final_score < 50).scalar() or 0

        # Industry breakdown
        industry_q = scoped_company_query().with_entities(
            Company.industry, func.count(Company.id)
        ).filter(Company.industry.isnot(None)).group_by(
            Company.industry
        ).order_by(func.count(Company.id).desc()).limit(15)
        industry_breakdown = {row[0]: row[1] for row in industry_q.all()}

        # Country breakdown
        country_q = scoped_company_query().with_entities(
            Company.country, func.count(Company.id)
        ).filter(Company.country.isnot(None)).group_by(
            Company.country
        ).order_by(func.count(Company.id).desc()).limit(15)
        country_breakdown = {row[0]: row[1] for row in country_q.all()}

        return json.dumps({
            "totals": {
                "companies": total_companies,
                "contacts": total_contacts,
                "pipeline_runs": total_runs,
                "active_icps": total_icps,
            },
            "score_distribution": {
                "average_final_score": round(avg_final, 1) if avg_final else None,
                "high_score_leads": high_score,
                "medium_score_leads": medium_score,
                "low_score_leads": low_score,
            },
            "industry_breakdown": industry_breakdown,
            "country_breakdown": country_breakdown,
        })
    except Exception as e:
        logger.error(f"Get data statistics failed: {e}")
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@tool
def search_local_companies(
    industry: str = None,
    country: str = None,
    domain: str = None,
    min_employees: int = None,
    max_employees: int = None,
    limit: int = 50,
) -> str:
    """
    Search the local qlGen database for companies matching criteria.
    Returns companies from ALL previous pipeline runs.
    Use this BEFORE external tools to check what data already exists.

    Args:
        industry: Filter by industry (partial match, case-insensitive)
        country: Filter by country (partial match)
        domain: Filter by website domain (partial match)
        min_employees: Minimum employee count
        max_employees: Maximum employee count
        limit: Maximum results (default 50, max 100)

    Returns:
        JSON string with matching companies from the local database
    """
    limit = min(limit, 100)
    session = _get_sync_session()
    try:
        query = (
            session.query(Company)
            .options(joinedload(Company.contacts))
        )

        # Apply user scoping
        query = _apply_company_user_filter(query)

        if industry:
            query = query.filter(Company.industry.ilike(f"%{industry}%"))
        if country:
            query = query.filter(Company.country.ilike(f"%{country}%"))
        if domain:
            domain_clean = domain.lower().strip().removeprefix("www.").removeprefix("http://").removeprefix("https://")
            query = query.filter(func.lower(Company.website).contains(domain_clean))
        if min_employees is not None:
            query = query.filter(Company.employee_count >= min_employees)
        if max_employees is not None:
            query = query.filter(Company.employee_count <= max_employees)

        # Prefer companies with more data (final_score set, more recent)
        query = query.order_by(
            Company.final_score.desc().nullslast(),
            Company.created_at.desc(),
        )
        companies = query.limit(limit).all()

        results = []
        for c in companies:
            entry = _company_to_dict(c, include_contacts=False)
            entry["data_freshness"] = str(c.data_freshness) if c.data_freshness else str(c.created_at) if c.created_at else None
            entry["has_contacts"] = bool(c.contacts)
            entry["contact_count"] = len(c.contacts) if c.contacts else 0
            entry["pipeline_run_id"] = str(c.pipeline_run_id) if c.pipeline_run_id else None
            results.append(entry)

        return json.dumps({
            "count": len(results),
            "source": "local_database",
            "companies": results,
        })
    except Exception as e:
        logger.error(f"Local company search failed: {e}")
        return json.dumps({"error": str(e), "companies": []})
    finally:
        session.close()


@tool
def search_kb_companies(
    industry: str = None,
    country: str = None,
    domain: str = None,
    min_employees: int = None,
    max_employees: int = None,
    icp_description: str = None,
) -> str:
    """
    Search the Company Knowledge Base for companies matching criteria.
    Returns ONE canonical record per company domain, merged from ALL previous
    pipeline runs. This is deduplicated — no duplicate rows for the same company.
    Use this BEFORE external tools to check what data already exists.
    Returns ALL matching records (no artificial cap).

    When icp_description is provided, results are ranked by semantic similarity
    to the ICP (most relevant first). Otherwise results are ordered by recency.

    Args:
        industry: Filter by industry (partial match, case-insensitive)
        country: Filter by country (partial match)
        domain: Filter by website domain (partial match)
        min_employees: Minimum employee count
        max_employees: Maximum employee count
        icp_description: Natural language ICP description for relevance ranking.
            Pass the industry + geography + capability summary so results are
            ranked by fit to the CURRENT ICP, not historical scores.

    Returns:
        JSON string with matching companies from the knowledge base
    """
    session = _get_sync_session()
    try:
        # If ICP description provided, use semantic ranking via pgvector
        if icp_description:
            embedding = generate_embedding(icp_description[:8000])
            if embedding:
                return _search_kb_semantic_ranked(
                    session, embedding,
                    industry=industry, country=country, domain=domain,
                    min_employees=min_employees, max_employees=max_employees,
                )

        # Fallback: structured filter, ordered by most recently enriched
        query = session.query(CompanyKnowledgeBase)

        if industry:
            query = query.filter(CompanyKnowledgeBase.industry.ilike(f"%{industry}%"))
        if country:
            query = query.filter(CompanyKnowledgeBase.country.ilike(f"%{country}%"))
        if domain:
            domain_clean = domain.lower().strip().removeprefix("www.").removeprefix("http://").removeprefix("https://").rstrip("/")
            query = query.filter(CompanyKnowledgeBase.normalized_domain.contains(domain_clean))
        if min_employees is not None:
            query = query.filter(CompanyKnowledgeBase.employee_count >= min_employees)
        if max_employees is not None:
            query = query.filter(CompanyKnowledgeBase.employee_count <= max_employees)

        query = query.order_by(
            CompanyKnowledgeBase.last_enriched_at.desc().nullslast(),
        )
        records = query.all()

        results = []
        for kb in records:
            results.append({
                "name": kb.canonical_name,
                "website": kb.normalized_domain,
                "industry": kb.industry,
                "sub_industry": kb.sub_industry,
                "city": kb.city,
                "state_region": kb.state_region,
                "country": kb.country,
                "employee_count": kb.employee_count,
                "revenue_estimate": kb.revenue_estimate,
                "description": (kb.description or "")[:200],
                "source": "knowledge_base",
                "best_final_score": kb.best_final_score,
                "times_discovered": kb.times_discovered,
                "last_enriched_at": str(kb.last_enriched_at) if kb.last_enriched_at else None,
                "is_from_local_db": True,
            })

        return json.dumps({
            "count": len(results),
            "source": "knowledge_base",
            "ranking": "recency",
            "companies": results,
        })
    except Exception as e:
        logger.error(f"KB company search failed: {e}")
        return json.dumps({"error": str(e), "companies": []})
    finally:
        session.close()


def _search_kb_semantic_ranked(
    session, embedding: list[float],
    industry: str = None, country: str = None, domain: str = None,
    min_employees: int = None, max_employees: int = None,
) -> str:
    """Semantic-ranked KB search: filter by structured criteria, order by ICP similarity."""
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    # Build dynamic WHERE clauses
    where_clauses = ["kb.embedding IS NOT NULL"]
    params: dict = {"embedding": embedding_str}

    if industry:
        where_clauses.append("kb.industry ILIKE :industry")
        params["industry"] = f"%{industry}%"
    if country:
        where_clauses.append("kb.country ILIKE :country")
        params["country"] = f"%{country}%"
    if domain:
        domain_clean = domain.lower().strip().removeprefix("www.").removeprefix("http://").removeprefix("https://").rstrip("/")
        where_clauses.append("kb.normalized_domain LIKE :domain")
        params["domain"] = f"%{domain_clean}%"
    if min_employees is not None:
        where_clauses.append("kb.employee_count >= :min_emp")
        params["min_emp"] = min_employees
    if max_employees is not None:
        where_clauses.append("kb.employee_count <= :max_emp")
        params["max_emp"] = max_employees

    where_sql = " AND ".join(where_clauses)

    results = session.execute(
        text(f"""
            SELECT kb.canonical_name, kb.normalized_domain,
                   kb.industry, kb.sub_industry, kb.city, kb.state_region,
                   kb.country, kb.employee_count, kb.revenue_estimate,
                   kb.description, kb.best_final_score,
                   kb.times_discovered, kb.last_enriched_at,
                   1 - (kb.embedding <=> CAST(:embedding AS vector)) as icp_similarity
            FROM company_knowledge_base kb
            WHERE {where_sql}
            ORDER BY kb.embedding <=> CAST(:embedding AS vector)
        """),
        params,
    )

    companies = []
    for row in results:
        companies.append({
            "name": row.canonical_name,
            "website": row.normalized_domain,
            "industry": row.industry,
            "sub_industry": row.sub_industry,
            "city": row.city,
            "state_region": row.state_region,
            "country": row.country,
            "employee_count": row.employee_count,
            "revenue_estimate": row.revenue_estimate,
            "description": (row.description or "")[:200],
            "source": "knowledge_base",
            "best_final_score": row.best_final_score,
            "icp_similarity": round(row.icp_similarity, 4) if row.icp_similarity else None,
            "times_discovered": row.times_discovered,
            "last_enriched_at": str(row.last_enriched_at) if row.last_enriched_at else None,
            "is_from_local_db": True,
        })

    return json.dumps({
        "count": len(companies),
        "source": "knowledge_base",
        "ranking": "icp_similarity",
        "companies": companies,
    })


def _kb_record_to_dict(kb):
    """Serialize a CompanyKnowledgeBase ORM object to a dict."""
    return {
        "id": str(kb.id),
        "normalized_domain": kb.normalized_domain,
        "canonical_name": kb.canonical_name,
        "industry": kb.industry,
        "sub_industry": kb.sub_industry,
        "city": kb.city,
        "state_region": kb.state_region,
        "country": kb.country,
        "employee_count": kb.employee_count,
        "revenue_estimate": kb.revenue_estimate,
        "asset_value": kb.asset_value,
        "description": (kb.description or "")[:500],
        "best_icp_match_score": kb.best_icp_match_score,
        "best_budget_signal_score": kb.best_budget_signal_score,
        "best_urgency_signal_score": kb.best_urgency_signal_score,
        "best_final_score": kb.best_final_score,
        "best_deal_hotness_score": kb.best_deal_hotness_score,
        "best_deal_hotness_tier": kb.best_deal_hotness_tier,
        "times_discovered": kb.times_discovered,
        "best_known_contacts": kb.best_known_contacts,
        "last_enriched_at": str(kb.last_enriched_at) if kb.last_enriched_at else None,
    }


@tool
def search_knowledge_base(query: str, limit: int = 10) -> str:
    """
    Search the Company Knowledge Base using semantic similarity (vector search).
    The Knowledge Base contains ONE canonical 'golden record' per company domain,
    merged from ALL pipeline runs. Use this for cross-run company lookups.
    BEST FOR: Finding the best-known data about companies across all pipeline runs.

    Args:
        query: Natural language search query describing what you're looking for
        limit: Maximum number of results to return (default 10, max 25)

    Returns:
        JSON string with matching KB records and similarity scores
    """
    limit = min(limit, 25)
    embedding = generate_embedding(query)
    if not embedding is None:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    else:
        return json.dumps({"error": "Failed to generate embedding for query", "companies": []})

    session = _get_sync_session()
    try:
        results = session.execute(
            text("""
                SELECT kb.id, kb.normalized_domain, kb.canonical_name,
                       kb.industry, kb.sub_industry, kb.city, kb.state_region,
                       kb.country, kb.employee_count, kb.revenue_estimate,
                       kb.asset_value, kb.description,
                       kb.best_icp_match_score, kb.best_budget_signal_score,
                       kb.best_urgency_signal_score, kb.best_final_score,
                       kb.best_deal_hotness_score, kb.best_deal_hotness_tier,
                       kb.times_discovered, kb.last_enriched_at,
                       1 - (kb.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM company_knowledge_base kb
                WHERE kb.embedding IS NOT NULL
                ORDER BY kb.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """),
            {"embedding": embedding_str, "limit": limit},
        )

        companies = []
        for row in results:
            companies.append({
                "id": str(row.id),
                "normalized_domain": row.normalized_domain,
                "canonical_name": row.canonical_name,
                "industry": row.industry,
                "sub_industry": row.sub_industry,
                "city": row.city,
                "state_region": row.state_region,
                "country": row.country,
                "employee_count": row.employee_count,
                "revenue_estimate": row.revenue_estimate,
                "best_final_score": row.best_final_score,
                "best_deal_hotness_score": row.best_deal_hotness_score,
                "best_deal_hotness_tier": row.best_deal_hotness_tier,
                "times_discovered": row.times_discovered,
                "last_enriched_at": str(row.last_enriched_at) if row.last_enriched_at else None,
                "similarity": round(row.similarity, 4) if row.similarity else None,
            })

        return json.dumps({
            "source": "knowledge_base",
            "query": query,
            "count": len(companies),
            "companies": companies,
        })
    except Exception as e:
        logger.error(f"KB semantic search failed: {e}")
        return json.dumps({"error": str(e), "companies": []})
    finally:
        session.close()


@tool
def search_knowledge_base_structured(
    industry: str = None,
    country: str = None,
    min_score: float = None,
    min_employees: int = None,
    max_employees: int = None,
    limit: int = 20,
) -> str:
    """
    Search the Company Knowledge Base using structured filters.
    The Knowledge Base contains ONE canonical 'golden record' per company domain,
    merged from ALL pipeline runs. Use this for cross-run filtered lookups.
    BEST FOR: Filtering the best-known company data by industry, country, score, size.

    Args:
        industry: Filter by industry (partial match, case-insensitive)
        country: Filter by country (partial match)
        min_score: Minimum best_final_score (0-100)
        min_employees: Minimum employee count
        max_employees: Maximum employee count
        limit: Maximum results (default 20, max 50)

    Returns:
        JSON string with matching KB records
    """
    limit = min(limit, 50)
    session = _get_sync_session()
    try:
        query = session.query(CompanyKnowledgeBase)

        if industry:
            query = query.filter(CompanyKnowledgeBase.industry.ilike(f"%{industry}%"))
        if country:
            query = query.filter(CompanyKnowledgeBase.country.ilike(f"%{country}%"))
        if min_score is not None:
            query = query.filter(CompanyKnowledgeBase.best_final_score >= min_score)
        if min_employees is not None:
            query = query.filter(CompanyKnowledgeBase.employee_count >= min_employees)
        if max_employees is not None:
            query = query.filter(CompanyKnowledgeBase.employee_count <= max_employees)

        query = query.order_by(CompanyKnowledgeBase.best_final_score.desc().nullslast())
        records = query.limit(limit).all()

        results = [_kb_record_to_dict(r) for r in records]
        return json.dumps({
            "source": "knowledge_base",
            "count": len(results),
            "filters_applied": {
                k: v for k, v in {
                    "industry": industry, "country": country,
                    "min_score": min_score,
                    "min_employees": min_employees, "max_employees": max_employees,
                }.items() if v is not None
            },
            "companies": results,
        })
    except Exception as e:
        logger.error(f"KB structured search failed: {e}")
        return json.dumps({"error": str(e), "companies": []})
    finally:
        session.close()
