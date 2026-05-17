"""Firmographic filter service for ingest pipeline.

Researches imported companies using Apollo + web tools, evaluates firmographic
fit via Bedrock Claude for human-readable justifications, and persists all
events to IngestBatchLog for async replay (user can leave and come back).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.ingest_batch import IngestBatch
from app.models.ingest_batch_log import IngestBatchLog
from app.services.event_store import push_event

logger = logging.getLogger(__name__)
settings = get_settings()

_bedrock_client = None


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
    return _bedrock_client


# ──────────────────────────────────────────────────────────────────
# Event helpers
# ──────────────────────────────────────────────────────────────────

async def _emit(batch_id: str, event: dict, collector: list) -> None:
    """Push event to Redis (live SSE) and append to collector (DB persistence)."""
    await push_event(batch_id, event)
    collector.append(event)


async def _persist_logs_incremental(
    batch_id: UUID, event_collector: list, start_idx: int,
) -> None:
    """Persist events from start_idx onward to IngestBatchLog table.

    Called after each company completes so events are available for
    replay if the user navigates away and returns mid-processing.
    """
    from app.db.session import async_session

    if start_idx >= len(event_collector):
        return

    async with async_session() as db:
        for seq in range(start_idx, len(event_collector)):
            event_data = event_collector[seq]
            log = IngestBatchLog(
                ingest_batch_id=batch_id,
                event_type=event_data.get("type", "unknown"),
                event_data=event_data,
                sequence_number=seq,
            )
            db.add(log)
        await db.commit()


# ──────────────────────────────────────────────────────────────────
# Tool wrappers with event emission
# ──────────────────────────────────────────────────────────────────

async def _research_apollo(
    company_name: str, domain: str,
    batch_id: str, collector: list,
) -> dict | None:
    """Call Apollo company search and emit tool events."""
    await _emit(batch_id, {
        "type": "tool_start",
        "data": {
            "tool_name": "apollo_company_search",
            "display_name": "Apollo Company Search",
            "context": f"Looking up '{company_name or domain}' in Apollo B2B database",
            "company_name": company_name,
        },
    }, collector)

    try:
        from app.tools.apollo_tool import apollo_company_search

        query = company_name or domain
        raw = await asyncio.to_thread(
            apollo_company_search,
            query=query,
            per_page=5,
        )

        if not raw or raw.get("error") or raw.get("rate_limited"):
            await _emit(batch_id, {
                "type": "tool_result",
                "data": {
                    "tool_name": "apollo_company_search",
                    "result_preview": "No results found in Apollo",
                    "success": False,
                    "fields_found": [],
                    "company_name": company_name,
                },
            }, collector)
            return None

        orgs = raw.get("organizations", [])
        if not orgs:
            await _emit(batch_id, {
                "type": "tool_result",
                "data": {
                    "tool_name": "apollo_company_search",
                    "result_preview": "No matching organizations found",
                    "success": False,
                    "fields_found": [],
                    "company_name": company_name,
                },
            }, collector)
            return None

        # Pick best match
        best = orgs[0]
        if domain:
            for org in orgs:
                org_domain = (org.get("website_url") or "").replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
                if org_domain == domain:
                    best = org
                    break

        data = _parse_apollo_org(best)
        fields = [k for k, v in data.items() if v]

        await _emit(batch_id, {
            "type": "tool_result",
            "data": {
                "tool_name": "apollo_company_search",
                "result_preview": _format_research_preview(data),
                "success": True,
                "fields_found": fields,
                "company_name": company_name,
            },
        }, collector)

        return data

    except Exception as e:
        logger.warning(f"Apollo search failed for '{company_name}': {e}")
        await _emit(batch_id, {
            "type": "tool_result",
            "data": {
                "tool_name": "apollo_company_search",
                "result_preview": f"Search failed: {str(e)[:200]}",
                "success": False,
                "fields_found": [],
                "company_name": company_name,
            },
        }, collector)
        return None


async def _research_web(
    company_name: str, domain: str,
    batch_id: str, collector: list,
) -> dict | None:
    """Call multi-source web research and emit tool events."""
    await _emit(batch_id, {
        "type": "tool_start",
        "data": {
            "tool_name": "research_company",
            "display_name": "Web Research",
            "context": f"Multi-source research for '{company_name}' ({domain or 'no domain'})",
            "company_name": company_name,
        },
    }, collector)

    try:
        from app.tools.company_research_tool import research_company

        raw = await asyncio.to_thread(
            research_company,
            company_name=company_name,
            company_domain=domain,
        )

        if not raw or isinstance(raw, str):
            await _emit(batch_id, {
                "type": "tool_result",
                "data": {
                    "tool_name": "research_company",
                    "result_preview": "No data found from web research",
                    "success": False,
                    "fields_found": [],
                    "company_name": company_name,
                },
            }, collector)
            return None

        data = _parse_research_result(raw, domain)
        fields = [k for k, v in data.items() if v]

        await _emit(batch_id, {
            "type": "tool_result",
            "data": {
                "tool_name": "research_company",
                "result_preview": _format_research_preview(data),
                "success": True,
                "fields_found": fields,
                "company_name": company_name,
            },
        }, collector)

        return data

    except Exception as e:
        logger.warning(f"Web research failed for '{company_name}': {e}")
        await _emit(batch_id, {
            "type": "tool_result",
            "data": {
                "tool_name": "research_company",
                "result_preview": f"Research failed: {str(e)[:200]}",
                "success": False,
                "fields_found": [],
                "company_name": company_name,
            },
        }, collector)
        return None


# ──────────────────────────────────────────────────────────────────
# LLM evaluation with reasoning
# ──────────────────────────────────────────────────────────────────

EVAL_SYSTEM_PROMPT = """You evaluate a company's firmographic fit against specific criteria.
Respond ONLY with a JSON object (no markdown fences, no explanation outside JSON):

{
  "score": <integer 0-100>,
  "justification": "<2-3 sentence summary of overall fit>",
  "breakdown": {
    "industry": {"score": <0-30>, "reasoning": "<1 sentence>"},
    "geography": {"score": <0-20>, "reasoning": "<1 sentence>"},
    "employees": {"score": <0-25>, "reasoning": "<1 sentence>"},
    "revenue": {"score": <0-25>, "reasoning": "<1 sentence>"}
  }
}

Scoring guide:
- industry (30 pts): Exact match=30, related/partial=15, no match=0, unknown=0
- geography (20 pts): Country in target list=20, similar/nearby=10, no match=0, unknown=0
- employees (25 pts): Within range=25, within 2x margin=12, outside=0, unknown=0
- revenue (25 pts): Within range=25, within 2x margin=12, outside=0, unknown=0"""


def _build_eval_prompt(kb: CompanyKnowledgeBase, filter_config: dict) -> str:
    """Build the user prompt for LLM evaluation."""
    industries = filter_config.get("industry_types", [])
    industry_str = ", ".join(
        f"{e.get('vertical', '')}" + (f" / {e['sub_vertical']}" if e.get("sub_vertical") else "")
        for e in industries
    ) or "Any"

    countries = filter_config.get("countries", [])
    emp = filter_config.get("employee_range", {})
    rev = filter_config.get("revenue_range", {})

    def fmt_rev(v):
        if not v:
            return "Not specified"
        if v >= 1e9:
            return f"${v/1e9:.1f}B"
        if v >= 1e6:
            return f"${v/1e6:.1f}M"
        return f"${v:,.0f}"

    return f"""Company data:
- Name: {kb.canonical_name or "Unknown"}
- Industry: {kb.industry or "Unknown"}{f" / {kb.sub_industry}" if kb.sub_industry else ""}
- Country: {kb.country or "Unknown"}
- City: {kb.city or "Unknown"}
- Employee Count: {kb.employee_count or "Unknown"}
- Revenue Estimate: {fmt_rev(kb.revenue_estimate)}
- Description: {(kb.description or "Not available")[:500]}

Target criteria:
- Industries: {industry_str}
- Countries: {", ".join(countries) or "Any"}
- Employee Range: {emp.get("min", "any")} - {emp.get("max", "any")}
- Revenue Range: {fmt_rev(rev.get("min"))} - {fmt_rev(rev.get("max"))} {rev.get("currency", "USD")}

Evaluate this company against the criteria."""


async def _evaluate_with_llm(
    kb: CompanyKnowledgeBase,
    filter_config: dict,
    batch_id: str,
    collector: list,
) -> dict | None:
    """Call Bedrock Claude to evaluate firmographic fit with reasoning."""
    try:
        user_prompt = _build_eval_prompt(kb, filter_config)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "system": EVAL_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 1024,
            "temperature": 0.2,
        })

        response = await asyncio.to_thread(
            _get_bedrock_client().invoke_model,
            modelId=settings.BEDROCK_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        text = result["content"][0]["text"]

        # Emit the reasoning as agent_reasoning event
        await _emit(batch_id, {
            "type": "agent_reasoning",
            "data": {
                "text": text,
                "company_name": kb.canonical_name or "",
            },
        }, collector)

        # Parse JSON from response
        parsed = _extract_json(text)
        return parsed

    except Exception as e:
        logger.warning(f"LLM evaluation failed for {kb.canonical_name}: {e}")
        return None


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        closing = text.rfind("```")
        if closing != -1:
            text = text[:closing]
        text = text.strip()

    start = text.index("{")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    return json.loads(text[start:])


# ──────────────────────────────────────────────────────────────────
# Deterministic scoring (fallback if LLM fails)
# ──────────────────────────────────────────────────────────────────

def score_firmographic_fit(kb: CompanyKnowledgeBase, filter_config: dict) -> dict:
    """Programmatic scoring — used as fallback when LLM evaluation fails."""
    ind = _score_industry_val(kb, filter_config)
    geo = _score_geography_val(kb, filter_config)
    emp = _score_range_val(kb.employee_count, filter_config.get("employee_range", {}))
    rev = _score_range_val(kb.revenue_estimate, filter_config.get("revenue_range", {}))

    return {
        "score": ind["score"] + geo["score"] + emp["score"] + rev["score"],
        "justification": f"Programmatic evaluation: industry {ind['score']}/30, "
                         f"geography {geo['score']}/20, employees {emp['score']}/25, "
                         f"revenue {rev['score']}/25.",
        "breakdown": {
            "industry": ind,
            "geography": geo,
            "employees": emp,
            "revenue": rev,
        },
    }


def _score_industry_val(kb: CompanyKnowledgeBase, config: dict) -> dict:
    industry_types = config.get("industry_types", [])
    if not industry_types:
        return {"score": 30, "reasoning": "No industry criteria specified — full score."}

    company_ind = (kb.industry or "").lower().strip()
    if not company_ind:
        return {"score": 0, "reasoning": "Company industry is unknown."}

    for entry in industry_types:
        vertical = (entry.get("vertical") or "").lower().strip()
        if not vertical:
            continue
        if company_ind == vertical:
            return {"score": 30, "reasoning": f"Industry '{kb.industry}' matches target '{entry.get('vertical')}'."}
        if vertical in company_ind or company_ind in vertical:
            return {"score": 15, "reasoning": f"Industry '{kb.industry}' partially matches target '{entry.get('vertical')}'."}

    return {"score": 0, "reasoning": f"Industry '{kb.industry}' doesn't match any target industry."}


def _score_geography_val(kb: CompanyKnowledgeBase, config: dict) -> dict:
    countries = config.get("countries", [])
    if not countries:
        return {"score": 20, "reasoning": "No geography criteria specified — full score."}

    company_country = (kb.country or "").lower().strip()
    if not company_country:
        return {"score": 0, "reasoning": "Company country is unknown."}

    countries_lower = [c.lower().strip() for c in countries]
    if company_country in countries_lower:
        return {"score": 20, "reasoning": f"Country '{kb.country}' matches target geography."}

    return {"score": 0, "reasoning": f"Country '{kb.country}' is not in the target list."}


def _score_range_val(value: int | None, range_config: dict) -> dict:
    range_min = range_config.get("min")
    range_max = range_config.get("max")
    if range_min is None and range_max is None:
        return {"score": 25, "reasoning": "No range criteria specified — full score."}
    if value is None or value <= 0:
        return {"score": 0, "reasoning": "Value is unknown."}

    range_min = range_min or 0
    range_max = range_max or float("inf")

    if range_min <= value <= range_max:
        return {"score": 25, "reasoning": f"Value {value:,} is within target range."}

    margin_min = range_min / 2 if range_min > 0 else 0
    margin_max = range_max * 2 if range_max != float("inf") else float("inf")
    if margin_min <= value <= margin_max:
        return {"score": 12, "reasoning": f"Value {value:,} is close to target range (within 2x margin)."}

    return {"score": 0, "reasoning": f"Value {value:,} is outside target range."}


# ──────────────────────────────────────────────────────────────────
# Result parsers (from company_research_service.py)
# ──────────────────────────────────────────────────────────────────

def _parse_apollo_org(org: dict) -> dict:
    data: dict = {}
    website = org.get("website_url") or ""
    if website:
        d = website.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        if d:
            data["domain"] = d
    if org.get("industry"):
        data["industry"] = org["industry"]
    if org.get("country"):
        data["country"] = org["country"]
    if org.get("city"):
        data["city"] = org["city"]
    emp = org.get("estimated_num_employees")
    if emp and isinstance(emp, (int, float)):
        data["employee_count"] = int(emp)
    revenue = org.get("annual_revenue")
    if revenue and isinstance(revenue, (int, float)):
        data["revenue_estimate"] = int(revenue)
    desc = org.get("short_description")
    if desc:
        data["description"] = desc[:2000]
    return data


def _parse_research_result(raw: dict, existing_domain: str) -> dict:
    import re
    data: dict = {}
    rd = raw.get("company_domain", "")
    if rd and not existing_domain:
        data["domain"] = rd.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
    if raw.get("description"):
        data["description"] = raw["description"][:2000]
    tech = raw.get("tech_signals")
    if tech and isinstance(tech, list):
        data["tech_stack"] = tech[:30]
    financials = raw.get("financials", {})
    emp_signals = financials.get("employee_signals", [])
    for sig in emp_signals:
        text = sig if isinstance(sig, str) else str(sig)
        nums = re.findall(r"(\d[\d,]+)", text)
        for n in nums:
            val = int(n.replace(",", ""))
            if 10 < val < 10_000_000:
                data["employee_count"] = val
                break
        if "employee_count" in data:
            break
    rev_signals = financials.get("revenue_signals", [])
    for sig in rev_signals:
        text = sig.get("text", "") if isinstance(sig, dict) else str(sig)
        match = re.search(r"\$\s*([\d,.]+)\s*(billion|million|B|M)", text, re.IGNORECASE)
        if match:
            amount = float(match.group(1).replace(",", ""))
            unit = match.group(2).lower()
            if unit in ("billion", "b"):
                data["revenue_estimate"] = int(amount * 1e9)
            elif unit in ("million", "m"):
                data["revenue_estimate"] = int(amount * 1e6)
            break
    return data


def _format_research_preview(data: dict) -> str:
    """Build a human-readable summary of researched fields."""
    parts = []
    if data.get("industry"):
        parts.append(f"Industry: {data['industry']}")
    if data.get("country"):
        parts.append(f"Country: {data['country']}")
    if data.get("employee_count"):
        parts.append(f"Employees: {data['employee_count']:,}")
    if data.get("revenue_estimate"):
        rev = data["revenue_estimate"]
        if rev >= 1e9:
            parts.append(f"Revenue: ${rev/1e9:.1f}B")
        elif rev >= 1e6:
            parts.append(f"Revenue: ${rev/1e6:.1f}M")
        else:
            parts.append(f"Revenue: ${rev:,.0f}")
    if data.get("description"):
        parts.append(f"Description: {data['description'][:100]}...")
    return "; ".join(parts) if parts else "No firmographic data found"


# ──────────────────────────────────────────────────────────────────
# Apply researched data to KB record
# ──────────────────────────────────────────────────────────────────

def _apply_research_to_kb(kb: CompanyKnowledgeBase, *data_dicts: dict | None) -> list[str]:
    """Merge researched data into KB record. Only overwrites empty fields.
    Returns list of updated field names."""
    field_map = {
        "domain": "normalized_domain",
        "industry": "industry",
        "sub_industry": "sub_industry",
        "country": "country",
        "city": "city",
        "employee_count": "employee_count",
        "revenue_estimate": "revenue_estimate",
        "description": "description",
        "tech_stack": "tech_stack_json",
    }
    updated = []
    merged: dict = {}
    for d in data_dicts:
        if d:
            for k, v in d.items():
                if v and k not in merged:
                    merged[k] = v

    for research_key, kb_field in field_map.items():
        current = getattr(kb, kb_field, None)
        new_val = merged.get(research_key)
        if new_val and not current:
            setattr(kb, kb_field, new_val)
            updated.append(research_key)
    return updated


# ──────────────────────────────────────────────────────────────────
# Main orchestrator
# ──────────────────────────────────────────────────────────────────

async def evaluate_companies_firmographic(
    batch_id_str: str,
    company_kb_ids: list[UUID],
    filter_config: dict,
) -> None:
    """Background task: research each company, evaluate with LLM, persist events.

    Creates its own DB sessions. Emits SSE events for live streaming and
    persists them to IngestBatchLog for async replay.
    """
    from app.db.session import async_session

    total = len(company_kb_ids)
    scored_companies: list[dict] = []
    event_collector: list[dict] = []
    batch_uuid = UUID(batch_id_str)

    persisted_up_to = 0  # track how far we've persisted to DB

    for idx, kb_id in enumerate(company_kb_ids):
        async with async_session() as db:
            try:
                # Fetch company
                result = await db.execute(
                    select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == kb_id)
                )
                kb = result.scalar_one_or_none()
                if not kb:
                    continue

                company_name = kb.canonical_name or kb.normalized_domain or ""
                domain = kb.normalized_domain or ""

                # Emit company_start
                await _emit(batch_id_str, {
                    "type": "company_start",
                    "data": {
                        "company_name": company_name,
                        "company_kb_id": str(kb_id),
                        "company_index": idx + 1,
                        "total": total,
                        "percent": round((idx) / total * 100),
                    },
                }, event_collector)

                # ── Research phase ──
                apollo_data = await _research_apollo(
                    company_name, domain, batch_id_str, event_collector,
                )

                # Check what's still missing after Apollo
                missing_after_apollo = []
                merged = {**(apollo_data or {})}
                for field in ["industry", "country", "employee_count", "revenue_estimate"]:
                    if not getattr(kb, field, None) and not merged.get(field):
                        missing_after_apollo.append(field)

                web_data = None
                if missing_after_apollo:
                    web_data = await _research_web(
                        company_name, domain or merged.get("domain", ""),
                        batch_id_str, event_collector,
                    )

                # Apply research to KB
                updated_fields = _apply_research_to_kb(kb, apollo_data, web_data)
                if updated_fields:
                    await db.commit()

                # Re-fetch with updated fields
                await db.refresh(kb)

                # ── Evaluation phase ──
                llm_result = await _evaluate_with_llm(
                    kb, filter_config, batch_id_str, event_collector,
                )

                if llm_result and "score" in llm_result:
                    score_data = llm_result
                else:
                    # Fallback to programmatic scoring
                    score_data = score_firmographic_fit(kb, filter_config)
                    await _emit(batch_id_str, {
                        "type": "agent_reasoning",
                        "data": {
                            "text": score_data["justification"],
                            "company_name": company_name,
                        },
                    }, event_collector)

                # Build scored company result
                scored = {
                    "company_kb_id": str(kb_id),
                    "company_name": company_name,
                    "domain": kb.normalized_domain,
                    "industry": kb.industry,
                    "country": kb.country,
                    "employee_count": kb.employee_count,
                    "revenue_estimate": kb.revenue_estimate,
                    "score": score_data.get("score", 0),
                    "justification": score_data.get("justification", ""),
                    "score_breakdown": score_data.get("breakdown", {}),
                }
                scored_companies.append(scored)

                # Emit company_result
                await _emit(batch_id_str, {
                    "type": "company_result",
                    "data": scored,
                }, event_collector)

            except Exception as e:
                logger.warning(f"Firmographic eval failed for {kb_id}: {e}")
                # Emit a minimal result so the company isn't silently dropped
                await _emit(batch_id_str, {
                    "type": "company_result",
                    "data": {
                        "company_kb_id": str(kb_id),
                        "company_name": "",
                        "score": 0,
                        "justification": f"Evaluation failed: {str(e)[:200]}",
                        "score_breakdown": {},
                    },
                }, event_collector)

        # ── Persist this company's events to DB (incremental) ──
        try:
            await _persist_logs_incremental(batch_uuid, event_collector, persisted_up_to)
            persisted_up_to = len(event_collector)
        except Exception as e:
            logger.warning(f"Incremental log persist failed for batch {batch_id_str}: {e}")

    # Update batch record
    above_threshold = len([c for c in scored_companies if c.get("score", 0) >= 40])

    async with async_session() as db:
        batch_result = await db.execute(
            select(IngestBatch).where(IngestBatch.id == batch_uuid)
        )
        batch = batch_result.scalar_one_or_none()
        if batch:
            batch.enriched_count = len(scored_companies)
            batch.filtered_count = above_threshold
            batch.status = "completed"
            await db.commit()

    # Emit completion
    await _emit(batch_id_str, {
        "type": "firmographic_completed",
        "data": {
            "batch_id": batch_id_str,
            "scored_companies": scored_companies,
            "total": total,
            "above_threshold": above_threshold,
        },
    }, event_collector)

    # Persist final completion event to DB
    try:
        await _persist_logs_incremental(batch_uuid, event_collector, persisted_up_to)
    except Exception as e:
        logger.warning(f"Final log persist failed for batch {batch_id_str}: {e}")

    logger.info(
        f"Firmographic evaluation complete for batch {batch_id_str}: "
        f"{total} companies, {above_threshold} above threshold"
    )
