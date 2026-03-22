"""Company Knowledge Base service.

Maintains one canonical 'golden record' per unique company domain by
auto-merging the richest data from all pipeline runs.
"""
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.contact import Contact

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Domain normalisation (shared with pipeline_service)
# ──────────────────────────────────────────────────────────────────

def normalize_domain(domain: str) -> str:
    """Normalize a domain for KB lookup: strip scheme, www, trailing slash."""
    d = domain.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/")


# ──────────────────────────────────────────────────────────────────
# Contact deduplication helpers
# ──────────────────────────────────────────────────────────────────

def _normalize_contact_name(name: str) -> str:
    n = re.sub(r"\b[A-Z]\.\s*", "", name.strip())
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n


def _deduplicate_and_rank_contacts(existing: list[dict], new_contacts: list[dict], max_keep: int = 10) -> list[dict]:
    """Deduplicate contacts by email > linkedin > name, keep top N by confidence."""
    email_idx: dict[str, int] = {}
    linkedin_idx: dict[str, int] = {}
    name_idx: dict[str, int] = {}
    merged: list[dict] = []

    def _merge_into(target: dict, source: dict):
        for k, v in source.items():
            if v is not None and v != "" and not target.get(k):
                target[k] = v
        src_conf = source.get("confidence") or 0
        tgt_conf = target.get("confidence") or 0
        if src_conf > tgt_conf:
            target["confidence"] = src_conf

    for contact in existing + new_contacts:
        email = (contact.get("email") or "").lower().strip()
        linkedin = (contact.get("linkedin_url") or "").lower().strip().rstrip("/")
        name = contact.get("full_name") or ""
        name_norm = _normalize_contact_name(name) if name else ""

        matched_idx = None
        if email and email in email_idx:
            matched_idx = email_idx[email]
        elif linkedin and linkedin in linkedin_idx:
            matched_idx = linkedin_idx[linkedin]
        elif name_norm and name_norm in name_idx:
            matched_idx = name_idx[name_norm]

        if matched_idx is not None:
            _merge_into(merged[matched_idx], contact)
            if email:
                email_idx[email] = matched_idx
            if linkedin:
                linkedin_idx[linkedin] = matched_idx
        else:
            idx = len(merged)
            merged.append(dict(contact))
            if email:
                email_idx[email] = idx
            if linkedin:
                linkedin_idx[linkedin] = idx
            if name_norm:
                name_idx[name_norm] = idx

    # Sort by confidence desc, keep top N
    merged.sort(key=lambda c: c.get("confidence") or 0, reverse=True)
    return merged[:max_keep]


# ──────────────────────────────────────────────────────────────────
# Provenance tracking
# ──────────────────────────────────────────────────────────────────

def _update_provenance(existing_sources: dict | None, field: str, value, source_tool: str, run_id: str) -> dict:
    """Update per-field provenance tracking."""
    sources = dict(existing_sources) if existing_sources else {}
    sources[field] = {
        "value": value if not isinstance(value, (list, dict)) else str(value)[:200],
        "source_tool": source_tool,
        "run_id": run_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return sources


# ──────────────────────────────────────────────────────────────────
# Core: upsert_company_to_kb
# ──────────────────────────────────────────────────────────────────

async def upsert_company_to_kb(
    company: Company,
    contacts: list[Contact],
    run_id: UUID,
    db: AsyncSession,
) -> CompanyKnowledgeBase:
    """Find-or-create a KB record by normalized domain, then merge data.

    Merge strategy:
    - Firmographics: most recent non-null value wins
    - Scores: best-ever (max)
    - Contacts: deduplicate, keep top 10 by confidence
    - Embedding: latest pipeline run (freshest representation)
    - Provenance: per-field JSONB tracking
    """
    domain = company.website
    if not domain:
        return None

    norm_domain = normalize_domain(domain)
    if not norm_domain:
        return None

    run_id_str = str(run_id)
    source_tool = company.source or "pipeline"

    # Find existing KB record
    result = await db.execute(
        select(CompanyKnowledgeBase).where(
            CompanyKnowledgeBase.normalized_domain == norm_domain
        )
    )
    kb = result.scalar_one_or_none()

    if kb is None:
        # Create new record
        kb = CompanyKnowledgeBase(
            normalized_domain=norm_domain,
            canonical_name=company.name,
            pipeline_run_ids=[run_id_str],
            times_discovered=1,
            first_discovered_at=datetime.now(timezone.utc),
            data_sources={},
        )
        db.add(kb)
    else:
        # Update metadata
        kb.times_discovered = (kb.times_discovered or 0) + 1
        existing_runs = kb.pipeline_run_ids or []
        if run_id_str not in existing_runs:
            kb.pipeline_run_ids = existing_runs + [run_id_str]

    # ── Firmographic fields: most recent non-null wins ──
    provenance = dict(kb.data_sources) if kb.data_sources else {}

    firmographic_fields = [
        ("canonical_name", company.name),
        ("industry", company.industry),
        ("sub_industry", company.sub_industry),
        ("country", company.country),
        ("city", company.city),
        ("state_region", company.state_region),
        ("employee_count", company.employee_count),
        ("revenue_estimate", company.revenue_estimate),
        ("asset_value", company.asset_value),
        ("tech_stack_json", company.tech_stack_json),
        ("description", company.description),
    ]

    for field_name, new_value in firmographic_fields:
        if new_value is not None and new_value != "" and new_value != []:
            setattr(kb, field_name, new_value)
            provenance = _update_provenance(provenance, field_name, new_value, source_tool, run_id_str)

    # ── Scores: best-ever (max) ──
    score_fields = [
        ("best_icp_match_score", company.icp_match_score),
        ("best_budget_signal_score", company.budget_signal_score),
        ("best_urgency_signal_score", company.urgency_signal_score),
        ("best_final_score", company.final_score),
        ("best_deal_hotness_score", company.deal_hotness_score),
    ]

    for kb_field, company_value in score_fields:
        if company_value is not None:
            current = getattr(kb, kb_field)
            if current is None or company_value > current:
                setattr(kb, kb_field, company_value)
                provenance = _update_provenance(provenance, kb_field, company_value, source_tool, run_id_str)

    # Best deal hotness tier (from the run with highest hotness score)
    if company.deal_hotness_tier and company.deal_hotness_score is not None:
        if kb.best_deal_hotness_score is not None and company.deal_hotness_score >= kb.best_deal_hotness_score:
            kb.best_deal_hotness_tier = company.deal_hotness_tier

    # ── Contacts: deduplicate, keep top 10 ──
    existing_contacts = kb.best_known_contacts or []
    new_contact_dicts = [
        {
            "full_name": c.full_name,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "designation": c.designation,
            "role_category": c.role_category,
            "email": c.email,
            "phone": c.phone,
            "linkedin_url": c.linkedin_url,
            "source": c.source,
            "confidence": c.confidence,
        }
        for c in contacts
    ]
    kb.best_known_contacts = _deduplicate_and_rank_contacts(existing_contacts, new_contact_dicts)

    # ── Embedding: always from latest run ──
    if company.embedding is not None:
        kb.embedding = company.embedding

    # ── Provenance & timestamps ──
    kb.data_sources = provenance
    kb.last_enriched_at = datetime.now(timezone.utc)

    await db.flush()
    return kb


# ──────────────────────────────────────────────────────────────────
# Lookup by domain
# ──────────────────────────────────────────────────────────────────

async def lookup_from_kb(domain: str, db: AsyncSession) -> CompanyKnowledgeBase | None:
    """Fast unique-index lookup by normalized domain.

    No age limit — KB data is always canonical.
    """
    if not domain:
        return None

    norm_domain = normalize_domain(domain)
    if not norm_domain:
        return None

    result = await db.execute(
        select(CompanyKnowledgeBase).where(
            CompanyKnowledgeBase.normalized_domain == norm_domain
        )
    )
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────
# Clone KB data into a per-run Company
# ──────────────────────────────────────────────────────────────────

def clone_from_kb(kb_record: CompanyKnowledgeBase, company: Company):
    """Copy enriched data from a KB record to a new per-run Company."""
    if kb_record.employee_count and not company.employee_count:
        company.employee_count = kb_record.employee_count
    if kb_record.revenue_estimate and not company.revenue_estimate:
        company.revenue_estimate = kb_record.revenue_estimate
    if kb_record.asset_value and not company.asset_value:
        company.asset_value = kb_record.asset_value
    if kb_record.tech_stack_json and not company.tech_stack_json:
        company.tech_stack_json = kb_record.tech_stack_json
    if kb_record.description and not company.description:
        company.description = kb_record.description
    if kb_record.industry and not company.industry:
        company.industry = kb_record.industry
    if kb_record.sub_industry and not company.sub_industry:
        company.sub_industry = kb_record.sub_industry
    if kb_record.country and not company.country:
        company.country = kb_record.country
    if kb_record.city and not company.city:
        company.city = kb_record.city
    if kb_record.state_region and not company.state_region:
        company.state_region = kb_record.state_region
    if kb_record.embedding is not None and company.embedding is None:
        company.embedding = kb_record.embedding

    company.data_freshness = kb_record.last_enriched_at


# ──────────────────────────────────────────────────────────────────
# Semantic search on KB
# ──────────────────────────────────────────────────────────────────

async def search_kb_semantic(
    query_embedding: list[float],
    db: AsyncSession,
    limit: int = 100,
    threshold: float = 0.7,
) -> list[dict]:
    """pgvector cosine similarity search on the knowledge base."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    result = await db.execute(
        sa_text("""
            SELECT kb.normalized_domain, kb.canonical_name, kb.industry,
                   kb.sub_industry, kb.city, kb.state_region, kb.country,
                   kb.employee_count, kb.revenue_estimate,
                   kb.description, kb.best_final_score,
                   1 - (kb.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM company_knowledge_base kb
            WHERE kb.embedding IS NOT NULL
              AND 1 - (kb.embedding <=> CAST(:embedding AS vector)) > :threshold
            ORDER BY kb.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """),
        {
            "embedding": embedding_str,
            "threshold": threshold,
            "limit": limit,
        },
    )
    rows = result.fetchall()

    return [
        {
            "name": row.canonical_name,
            "website": row.normalized_domain,
            "industry": row.industry or "",
            "sub_industry": row.sub_industry or "",
            "city": row.city or "",
            "state": row.state_region or "",
            "country": row.country or "",
            "employee_count": row.employee_count,
            "revenue_estimate": row.revenue_estimate,
            "description": row.description or "",
            "source": f"kb_preseed (similarity={row.similarity:.2f})",
        }
        for row in rows
    ]


# ──────────────────────────────────────────────────────────────────
# Structured search on KB
# ──────────────────────────────────────────────────────────────────

async def search_kb_structured(
    db: AsyncSession,
    industry: str | None = None,
    country: str | None = None,
    min_score: float | None = None,
    min_employees: int | None = None,
    max_employees: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CompanyKnowledgeBase]:
    """Filtered search on the knowledge base."""
    query = select(CompanyKnowledgeBase)

    if industry:
        query = query.where(CompanyKnowledgeBase.industry.ilike(f"%{industry}%"))
    if country:
        query = query.where(CompanyKnowledgeBase.country.ilike(f"%{country}%"))
    if min_score is not None:
        query = query.where(CompanyKnowledgeBase.best_final_score >= min_score)
    if min_employees is not None:
        query = query.where(CompanyKnowledgeBase.employee_count >= min_employees)
    if max_employees is not None:
        query = query.where(CompanyKnowledgeBase.employee_count <= max_employees)

    query = query.order_by(CompanyKnowledgeBase.best_final_score.desc().nullslast())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


# ──────────────────────────────────────────────────────────────────
# One-time backfill from existing runs
# ──────────────────────────────────────────────────────────────────

async def backfill_kb_from_existing_runs(db: AsyncSession) -> int:
    """Iterate all companies with final_score, ordered by created_at ASC
    (oldest first so newest wins on merge), and upsert each into KB.

    Returns the number of companies processed.
    """
    from sqlalchemy.orm import selectinload

    batch_size = 100
    offset = 0
    total_processed = 0

    while True:
        result = await db.execute(
            select(Company)
            .where(Company.final_score.isnot(None))
            .options(selectinload(Company.contacts))
            .order_by(Company.created_at.asc())
            .offset(offset)
            .limit(batch_size)
        )
        companies = list(result.scalars().unique().all())
        if not companies:
            break

        for company in companies:
            if not company.website:
                continue
            try:
                await upsert_company_to_kb(
                    company,
                    list(company.contacts) if company.contacts else [],
                    company.pipeline_run_id,
                    db,
                )
                total_processed += 1
            except Exception as e:
                logger.warning(f"KB backfill failed for company {company.id}: {e}")

        await db.commit()
        offset += batch_size
        logger.info(f"KB backfill: processed {total_processed} companies so far")

    logger.info(f"KB backfill complete: {total_processed} companies processed")
    return total_processed
