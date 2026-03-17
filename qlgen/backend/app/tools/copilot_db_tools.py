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
