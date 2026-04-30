"""5-stage pipeline orchestration with mandatory user review gates.

Stage 1: Industry Discovery (automatic)
Stage 2: Firmographic Fit Check (automatic → pause for review)
Stage 3: Budget & Urgency Signals (flexible: serial or parallel → pause)
Stage 4: Contact Discovery (automatic)
Stage 5: Final Scoring & Ranking (computation)
"""
import asyncio
import json
import logging
import re
import traceback
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.agent.lead_gen_agent import (
    create_industry_discovery_agent,
    create_discovery_sub_agent_db,
    create_discovery_sub_agent_web,
    create_discovery_sub_agent_evaboot,
    create_firmographic_fit_agent,
    create_signal_agent,
    create_contact_agent,
    create_pipeline_callback_handler,
    compute_final_score,
    PipelineCancelled,
)
from app.agent.prompt_builder import (
    build_industry_discovery_prompt,
    build_discovery_web_prompt,
    build_firmographic_fit_prompt,
    build_signal_prompt,
    build_batch_signal_prompt,
    build_contact_discovery_prompt,
)
from app.db.session import async_session
from app.models.pipeline import PipelineRun
from app.models.icp import ICPConfig
from app.models.company import Company
from app.models.contact import Contact
from app.models.company_stage import CompanyStageResult
from app.models.pipeline_log import PipelineLog
from app.services.tool_registry_service import get_disabled_tool_names
from app.services.validation_service import validate_stage_companies, validate_stage_contacts, compute_data_quality_score
from app.services.intelligence_service import get_intelligence_for_icp, format_intelligence_for_prompt
from app.services import event_store

logger = logging.getLogger(__name__)


def _safe_int(value) -> int | None:
    """Coerce a value to int, returning None if it can't be converted.

    The AI agent sometimes returns descriptive strings like
    'Unknown (estimated 50-200 based on company profile)' for numeric
    fields. This helper extracts the first number from such strings
    or returns None so the DB write doesn't fail.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        # Try direct conversion first (e.g. "1500")
        cleaned = value.replace(",", "").strip()
        try:
            return int(cleaned)
        except ValueError:
            pass
        # Try to extract the first number from the string
        match = re.search(r"[\d,]+", value)
        if match:
            try:
                return int(match.group().replace(",", ""))
            except ValueError:
                pass
    return None


def _safe_str(value, max_length: int = 500) -> str | None:
    """Truncate agent-returned strings to fit column width."""
    if value is None:
        return None
    s = str(value).strip()
    return s[:max_length] if s else None


# ──────────────────────────────────────────────────────────────────
# C4: Embedding-powered discovery pre-seeding
# ──────────────────────────────────────────────────────────────────

async def _preseed_from_embeddings(
    db,
    icp: dict,
    current_run_id: UUID,
    similarity_threshold: float = 0.7,
    max_seed: int = 100,
) -> list[dict]:
    """Search the Company Knowledge Base via pgvector similarity to the ICP description.

    Generates an embedding from the ICP text and finds semantically similar
    companies from the KB (canonical golden records). Returns them as dicts
    compatible with the Stage 1 discovery format.
    """
    from app.services.embedding_service import generate_embedding
    from app.services.company_kb_service import search_kb_semantic
    from app.agent.prompt_builder import build_industry_discovery_prompt

    icp_text = build_industry_discovery_prompt(icp)
    icp_text = icp_text[:8000]
    embedding = generate_embedding(icp_text)
    if not embedding:
        logger.warning("Could not generate ICP embedding for pre-seeding")
        return []

    seed_companies = await search_kb_semantic(
        query_embedding=embedding,
        db=db,
        limit=max_seed,
        threshold=similarity_threshold,
    )

    logger.info(f"KB pre-seed: found {len(seed_companies)} similar companies from knowledge base")
    return seed_companies


# ──────────────────────────────────────────────────────────────────
# Evaboot / Sales Navigator helpers
# ──────────────────────────────────────────────────────────────────

async def _run_evaboot_extraction(
    run_id_str: str,
    sales_navigator_url: str,
    event_collector: list,
    disabled_tools: set[str] | None,
    max_credits: int = 500,
) -> tuple[list[dict], int]:
    """Run Evaboot extraction and return (companies, credits_used).

    Starts extraction, polls for completion, then parses prospects into
    the standard company dict format used by Stage 1.
    """
    from app.agent.prompt_builder import build_industry_discovery_prompt
    from app.tools.evaboot_tool import (
        evaboot_check_quota as _check_quota,
        evaboot_extract_from_url as _extract,
        evaboot_get_extraction_status as _get_status,
        evaboot_get_extraction_results as _get_results,
    )

    # Pre-flight credit check
    await _emit_event(run_id_str, {
        "type": "stage_update",
        "stage": "industry_discovery",
        "progress": 8,
        "message": "Stage 1 (Evaboot): Checking available credits...",
    })

    raw_quota = _check_quota()
    if "error" in raw_quota:
        raise ValueError(f"Evaboot credit check failed: {raw_quota['error']}")

    # Evaboot API nests data under "quota" key: {"success": true, "quota": {...}}
    quota = raw_quota.get("quota", raw_quota)

    available_credits = quota.get("credits", 0)
    if available_credits < 10:
        raise ValueError(
            f"Insufficient Evaboot credits ({available_credits} remaining). "
            f"Need at least 10 credits to run an extraction."
        )

    logger.info(f"[Evaboot] Credits available: {available_credits}, daily remaining: {quota.get('remaining', '?')}")

    # Start extraction
    await _emit_event(run_id_str, {
        "type": "stage_update",
        "stage": "industry_discovery",
        "progress": 10,
        "message": "Stage 1 (Evaboot): Starting Sales Navigator extraction...",
    })

    extraction = _extract(
        linkedin_url=sales_navigator_url,
        search_name=f"pipeline_{run_id_str[:8]}",
        enrich_email="all",
    )
    if "error" in extraction:
        raise ValueError(f"Evaboot extraction failed: {extraction['error']}")

    extraction_id = extraction.get("id") or extraction.get("extraction_id")
    if not extraction_id:
        raise ValueError(f"Evaboot did not return an extraction ID: {extraction}")

    logger.info(f"[Evaboot] Extraction started: {extraction_id}")

    # Poll for completion (max 10 minutes)
    max_polls = 60
    poll_interval = 10
    for i in range(max_polls):
        await asyncio.sleep(poll_interval)

        status_resp = _get_status(str(extraction_id))
        if "error" in status_resp:
            logger.warning(f"[Evaboot] Status poll error: {status_resp['error']}")
            continue

        status = (status_resp.get("status") or "").lower()
        progress_pct = min(10 + (i * 10 // max_polls), 20)

        await _emit_event(run_id_str, {
            "type": "stage_update",
            "stage": "industry_discovery",
            "progress": progress_pct,
            "message": f"Stage 1 (Evaboot): Extraction {status}... (poll {i+1})",
        })

        # Evaboot uses "executed" (not "complete") for finished extractions
        if status in ("complete", "executed", "done", "finished"):
            break
        elif status in ("failed", "error"):
            error_msg = status_resp.get("error", "Unknown error")
            raise ValueError(f"Evaboot extraction failed: {error_msg}")
    else:
        raise ValueError("Evaboot extraction timed out after 10 minutes")

    # Get results — status response may already contain prospects
    prospects = status_resp.get("prospects", [])
    if not prospects:
        results = _get_results(str(extraction_id))
        if "error" in results:
            raise ValueError(f"Evaboot results retrieval failed: {results['error']}")
        prospects = results.get("prospects", [])
    logger.info(f"[Evaboot] Extraction complete: {len(prospects)} prospects")

    await _emit_event(run_id_str, {
        "type": "stage_update",
        "stage": "industry_discovery",
        "progress": 22,
        "message": f"Stage 1 (Evaboot): Extracted {len(prospects)} prospects from Sales Navigator",
    })

    # Parse prospects into company dicts
    companies = _parse_evaboot_prospects(prospects)
    credits_used = len(prospects)  # 1 credit/profile (+ email enrichment counted separately)

    return companies, credits_used


def _safe_float(value) -> float | None:
    """Coerce a value to float, returning None if it can't be converted."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("%", "")
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_revenue_millions(value) -> int | None:
    """Parse a revenue value expressed in millions to dollars (×1,000,000)."""
    f = _safe_float(value)
    if f is None:
        return None
    return int(f * 1_000_000)


def _parse_comma_list(value) -> list[str]:
    """Split a comma-separated string into a list of stripped strings."""
    if not value:
        return []
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _parse_department_headcounts(value) -> dict[str, int] | None:
    """Parse department headcount data.

    Handles formats like:
    - 'Sales: 5\\nEngineering: 6'
    - dict already
    - JSON string
    """
    if not value:
        return None
    if isinstance(value, dict):
        return value
    s = str(value).strip()
    if not s:
        return None
    result = {}
    # Try key: value lines (newline or semicolon separated)
    for sep in ["\n", ";"]:
        if sep in s:
            for part in s.split(sep):
                if ":" in part:
                    k, v = part.split(":", 1)
                    parsed = _safe_int(v.strip())
                    if parsed is not None:
                        result[k.strip()] = parsed
            if result:
                return result
    # Single "key: value" pair
    if ":" in s:
        k, v = s.split(":", 1)
        parsed = _safe_int(v.strip())
        if parsed is not None:
            return {k.strip(): parsed}
    return None


def _parse_evaboot_prospects(prospects: list[dict]) -> list[dict]:
    """Convert Evaboot prospect data into the standard company dict format.

    Groups prospects by company domain/name to create unique company entries
    with their contacts.

    Evaboot API returns fields with display names like "Company Name",
    "Company Domain", etc.  We support both snake_case (legacy) and the
    actual API display-name format.
    """
    company_map = {}  # key: normalized domain or company name

    def _get(d: dict, *keys: str) -> str:
        """Return first non-empty value from multiple possible keys."""
        for k in keys:
            v = d.get(k)
            if v:
                return str(v).strip()
        return ""

    for p in prospects:
        company_name = _get(p, "Company Name", "current_company")
        company_domain = _get(p, "Company Domain", "current_company_domain", "Company Website URL", "company_website")

        # Create company key for dedup
        key = company_domain.lower() if company_domain else company_name.lower()
        if not key:
            continue

        if key not in company_map:
            employee_count = _safe_int(
                p.get("Company Employee Exact Count") or p.get("company_size")
            )

            # Revenue: stored in dollars (×1M from the Evaboot millions value)
            revenue_min = _parse_revenue_millions(
                p.get("Company Revenue Min (Millions USD)") or p.get("company_revenue_min")
            )
            revenue_max = _parse_revenue_millions(
                p.get("Company Revenue Max (Millions USD)") or p.get("company_revenue_max")
            )
            # Compute midpoint revenue estimate
            revenue_estimate = None
            if revenue_min is not None and revenue_max is not None:
                revenue_estimate = int((revenue_min + revenue_max) / 2)
            elif revenue_min is not None:
                revenue_estimate = revenue_min
            elif revenue_max is not None:
                revenue_estimate = revenue_max

            # LinkedIn data JSONB (semi-structured fields)
            linkedin_data = {
                "department_headcounts": _parse_department_headcounts(
                    p.get("Department Headcounts") or p.get("department_headcounts")
                ),
                "specialties": _parse_comma_list(
                    _get(p, "Company Specialities", "company_specialties")
                ) or None,
                "employee_growth_6m_pct": _safe_float(
                    p.get("Company Employee Growth 6 Months (%)") or p.get("employee_growth_6m")
                ),
                "employee_growth_2y_pct": _safe_float(
                    p.get("Company Employee Growth 2 Years (%)") or p.get("employee_growth_2y")
                ),
                "profile_picture_url": _get(p, "Company Profile Picture", "company_profile_picture") or None,
                "revenue_currency": _get(p, "Company Revenue Currency", "revenue_currency") or None,
                "employee_range_text": _get(p, "Company Employee Range", "employee_range") or None,
                "company_type_detailed": _get(p, "Company Type", "company_type_detailed") or None,
                "matches_sn_filters": _get(p, "Matches Filters", "matches_filters") or None,
                "sn_no_match_reasons": _get(p, "No Match Reasons", "no_match_reasons") or None,
            }
            # Remove None values from linkedin_data for cleaner JSONB
            linkedin_data = {k: v for k, v in linkedin_data.items() if v is not None}

            company_map[key] = {
                "name": company_name,
                "website": company_domain or _get(p, "Company Website URL"),
                "industry": _get(p, "Company Industry", "company_industry"),
                "employee_count": employee_count,
                "city": None,
                "state_region": None,
                "country": None,
                "description": _get(p, "Company Description", "company_description"),
                "source": "evaboot",
                "discovery_method": "linkedin_sales_navigator",
                "contacts": [],
                # New dedicated columns
                "domain": company_domain.lower() if company_domain else None,
                "linkedin_url": _get(p, "Company Linkedin URL Unique ID", "company_linkedin_url") or None,
                "company_type": _get(p, "Company Type", "company_type") or None,
                "year_founded": _safe_int(p.get("Company Year Founded") or p.get("year_founded")),
                "revenue_min": revenue_min,
                "revenue_max": revenue_max,
                "revenue_estimate": revenue_estimate,
                "employee_growth_1y_pct": _safe_float(
                    p.get("Company Employee Growth 1 Year (%)") or p.get("employee_growth_1y")
                ),
                "funding_stage": _get(p, "Company Funding Stage", "funding_stage") or None,
                "headquarters_address": _get(p, "Company Headquarters (Full Address)", "headquarters_address") or None,
                "linkedin_data": linkedin_data if linkedin_data else None,
                "raw_prospect_data": p,  # Full raw payload for raw_data_json
            }

            # Parse location (use headquarters address as fallback)
            location = _get(p, "Company Location", "company_location", "location")
            hq_address = company_map[key]["headquarters_address"]
            loc_to_parse = location or hq_address or ""
            if loc_to_parse:
                parts = [part.strip() for part in loc_to_parse.split(",")]
                if len(parts) >= 3:
                    company_map[key]["city"] = parts[0]
                    company_map[key]["state_region"] = parts[-2]
                    company_map[key]["country"] = parts[-1]
                elif len(parts) == 2:
                    company_map[key]["city"] = parts[0]
                    company_map[key]["country"] = parts[-1]
                elif parts:
                    company_map[key]["country"] = parts[0]

        # Add contact — Evaboot company search results may not have person-level data
        full_name = _get(p, "Full Name", "full_name")
        if not full_name:
            first = _get(p, "First Name", "first_name")
            last = _get(p, "Last Name", "last_name")
            full_name = f"{first} {last}".strip()
        if full_name:
            company_map[key]["contacts"].append({
                "full_name": full_name,
                "first_name": _get(p, "First Name", "first_name"),
                "last_name": _get(p, "Last Name", "last_name"),
                "designation": _get(p, "Current Title", "current_title", "Title"),
                "email": _get(p, "Email", "email"),
                "phone": _get(p, "Phone", "phone"),
                "linkedin_url": _get(p, "Linkedin URL", "linkedin_url", "Profile URL"),
                "source": "evaboot",
                "email_validity": _get(p, "Email Status", "email_validity"),
            })

    return list(company_map.values())


# ──────────────────────────────────────────────────────────────────
# Utility functions
# ──────────────────────────────────────────────────────────────────

async def _emit_event(run_id: str, event: dict):
    """Push an SSE event to the Redis-backed event store."""
    await event_store.push_event(run_id, event)


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by closing open strings, arrays, and objects."""
    in_string = False
    escape_next = False
    stack = []

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    repaired = text
    if in_string:
        repaired += '"'
    for bracket in reversed(stack):
        repaired += '}' if bracket == '{' else ']'

    return repaired


def _truncate_to_last_complete_item(text: str) -> str:
    """Cut JSON text back to the last cleanly-closed array element."""
    last_obj_end = -1
    for marker in ['},\n', '},\r', '}, ']:
        pos = text.rfind(marker)
        if pos > last_obj_end:
            last_obj_end = pos

    if last_obj_end > 0:
        return text[: last_obj_end + 1]
    return text


def parse_json_from_agent_result(result) -> dict:
    """Extract JSON from the agent's text response, repairing truncation if needed."""
    text = str(result)

    if "```json" in text:
        start = text.index("```json") + 7
        closing = text.find("```", start)
        text = text[start:closing].strip() if closing != -1 else text[start:].strip()
    elif "```" in text:
        start = text.index("```") + 3
        closing = text.find("```", start)
        text = text[start:closing].strip() if closing != -1 else text[start:].strip()

    if "{" in text:
        start = text.index("{")
        depth = 0
        end = len(text)
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        repaired = _repair_truncated_json(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    try:
        truncated = _truncate_to_last_complete_item(text)
        repaired = _repair_truncated_json(truncated)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    logger.error(f"Failed to parse agent JSON (length={len(text)}). First 500 chars: {text[:500]}")
    return json.loads(text)


def _normalize_score_to_100(score: float | None) -> float | None:
    """Normalize a score to the 0-100 range.

    Clamps to [0, 100]. Does NOT auto-scale scores <= 10 because
    genuinely low scores (e.g., 5/100 or 8/100) were being inflated
    to 50 or 80. All stage prompts now explicitly require 0-100 scale.
    """
    if score is None:
        return None
    score = float(score)
    return min(100.0, max(0.0, score))


def _chunk(lst, size):
    """Split a list into chunks of given size."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# Company name suffixes to strip for normalization
_COMPANY_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|ltd\.?|limited|corp\.?|corporation|co\.?|"
    r"ag|gmbh|sa|s\.a\.?|plc|pty\.?|pvt\.?|bv|b\.v\.?|nv|n\.v\.?|"
    r"s\.r\.l\.?|s\.l\.?|aps|a/s|ab|oy|as)\s*$",
    re.IGNORECASE,
)


def _normalize_domain(domain: str) -> str:
    """Normalize a domain for dedup: strip scheme, www, trailing slash."""
    d = domain.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/")


def _normalize_company_name(name: str) -> str:
    """Normalize a company name for dedup: strip suffixes, punctuation, lowercase."""
    n = name.strip()
    n = _COMPANY_SUFFIXES.sub("", n).strip()
    n = re.sub(r"[,.\-\(\)]", " ", n)
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n


def _deduplicate_companies(companies: list[dict]) -> list[dict]:
    """Multi-layer company deduplication.

    Layer 1: Exact normalized domain match.
    Layer 2: Exact normalized name match.
    Layer 3: Fuzzy name matching (>85% similarity) via rapidfuzz.

    When duplicates are found, the entry with more non-null fields wins
    and gets metadata merged from the duplicate.
    """
    from rapidfuzz import fuzz

    # Track unique companies by index into result list
    result: list[dict] = []
    domain_index: dict[str, int] = {}  # normalized domain -> result index
    name_index: dict[str, int] = {}    # normalized name -> result index

    def _field_count(c: dict) -> int:
        """Count non-null, non-empty fields (more fields = richer data)."""
        return sum(1 for v in c.values() if v is not None and v != "" and v != [])

    def _merge_into(target: dict, source: dict):
        """Merge non-null fields from source into target."""
        for k, v in source.items():
            if v is not None and v != "" and v != [] and not target.get(k):
                target[k] = v

    for company in companies:
        domain_raw = company.get("website") or ""
        name_raw = company.get("name") or ""
        domain_norm = _normalize_domain(domain_raw) if domain_raw else ""
        name_norm = _normalize_company_name(name_raw) if name_raw else ""

        # Layer 1: Domain match
        if domain_norm and domain_norm in domain_index:
            idx = domain_index[domain_norm]
            existing = result[idx]
            if _field_count(company) > _field_count(existing):
                _merge_into(company, existing)
                result[idx] = company
            else:
                _merge_into(existing, company)
            continue

        # Layer 2: Exact name match
        if name_norm and name_norm in name_index:
            idx = name_index[name_norm]
            existing = result[idx]
            if _field_count(company) > _field_count(existing):
                _merge_into(company, existing)
                result[idx] = company
            else:
                _merge_into(existing, company)
            # Also register domain for this entry
            if domain_norm:
                domain_index[domain_norm] = idx
            continue

        # Layer 3: Fuzzy name match
        matched = False
        if name_norm and len(name_norm) > 3:
            for existing_name, idx in name_index.items():
                if fuzz.ratio(name_norm, existing_name) > 85:
                    existing = result[idx]
                    if _field_count(company) > _field_count(existing):
                        _merge_into(company, existing)
                        result[idx] = company
                    else:
                        _merge_into(existing, company)
                    if domain_norm:
                        domain_index[domain_norm] = idx
                    matched = True
                    break

        if matched:
            continue

        # No match found — add as new
        idx = len(result)
        result.append(company)
        if domain_norm:
            domain_index[domain_norm] = idx
        if name_norm:
            name_index[name_norm] = idx

    logger.info(f"Deduplication: {len(companies)} → {len(result)} unique companies")
    return result


def _soft_filter_discovered(companies: list[dict], icp: dict, label: str = "discovery") -> list[dict]:
    """Remove companies CLEARLY outside ICP hard bounds before saving to DB.

    Only filters when explicit numeric data is available (employee_count or
    revenue_estimate). Companies with no size data pass through unchanged
    (benefit of doubt). Uses generous hard bounds so only obvious mismatches
    are removed:
      - Employee: 0.3x min to 3x max
      - Revenue: 0.2x min to 5x max
    """
    fd = icp.get("firmographic_details", {})
    emp_range = fd.get("employee_range", {})
    rev_range = fd.get("revenue_range", {})

    emp_min = emp_range.get("min")
    emp_max = emp_range.get("max")
    rev_min = rev_range.get("min")
    rev_max = rev_range.get("max")

    # If ICP has no size criteria, skip filtering entirely
    if not emp_min and not emp_max and not rev_min and not rev_max:
        return companies

    # Compute hard bounds with generous margins
    emp_hard_min = int(emp_min * 0.3) if emp_min else None
    emp_hard_max = int(emp_max * 3) if emp_max else None
    rev_hard_min = int(rev_min * 0.2) if rev_min else None
    rev_hard_max = int(rev_max * 5) if rev_max else None

    kept = []
    removed = 0
    for c in companies:
        emp = _safe_int(c.get("employee_count"))
        rev = _safe_int(c.get("revenue_estimate"))

        # Only reject if we have data AND it's clearly outside hard bounds
        emp_outside = False
        if emp is not None:
            if emp_hard_min and emp < emp_hard_min:
                emp_outside = True
            if emp_hard_max and emp > emp_hard_max:
                emp_outside = True

        rev_outside = False
        if rev is not None:
            if rev_hard_min and rev < rev_hard_min:
                rev_outside = True
            if rev_hard_max and rev > rev_hard_max:
                rev_outside = True

        # Soft filter logic:
        # - If BOTH metrics are known and BOTH are outside → reject (clear mismatch)
        # - If only ONE metric is known and outside → keep (Stage 2 will verify)
        # - If neither is known → keep (benefit of doubt)
        # This is intentionally lenient to avoid dropping companies that Stage 2
        # might pass after deeper research.
        both_known = (emp is not None) and (rev is not None)
        if both_known and emp_outside and rev_outside:
            removed += 1
            continue
        # Single metric wildly outside bounds (>10x over max or <0.1x min) → reject
        if emp is not None and emp_outside and rev is None:
            if emp_hard_max and emp > emp_hard_max * 3:
                removed += 1
                continue
            if emp_hard_min and emp_hard_min > 0 and emp < emp_hard_min / 3:
                removed += 1
                continue
        if rev is not None and rev_outside and emp is None:
            if rev_hard_max and rev > rev_hard_max * 3:
                removed += 1
                continue
            if rev_hard_min and rev_hard_min > 0 and rev < rev_hard_min / 3:
                removed += 1
                continue

        kept.append(c)

    if removed:
        logger.info(f"[{label}] Soft filter: removed {removed} clearly out-of-range companies ({len(kept)} kept)")
    return kept


async def _carry_forward_from_previous_runs(
    db,
    icp_config_id: UUID,
    user_id: UUID | None,
    current_run_id: UUID,
    current_domains: set[str],
    current_names: set[str],
) -> list[dict]:
    """Carry forward non-disqualified companies from previous completed/reviewed runs of the same ICP.

    This ensures that repeated pipeline runs for the same ICP produce monotonically
    increasing company counts: all previously discovered companies are included
    alongside newly discovered ones.

    Args:
        db: Database session
        icp_config_id: The ICP config being run
        user_id: The user running the pipeline (multi-tenant safety)
        current_run_id: Current run ID (excluded from query)
        current_domains: Normalized domains already discovered in this run
        current_names: Normalized names already discovered in this run

    Returns:
        List of company dicts (discovery format) with source="carried_forward"
    """
    # Find previous completed or awaiting_review runs for the same ICP + user
    filters = [
        PipelineRun.icp_config_id == icp_config_id,
        PipelineRun.id != current_run_id,
        PipelineRun.status.in_(["completed", "awaiting_review"]),
    ]
    if user_id:
        filters.append(PipelineRun.user_id == user_id)

    prev_runs_result = await db.execute(
        select(PipelineRun.id).where(*filters)
    )
    prev_run_ids = [row[0] for row in prev_runs_result.all()]

    if not prev_run_ids:
        return []

    # Fetch non-disqualified companies from those runs
    prev_companies_result = await db.execute(
        select(Company).where(
            Company.pipeline_run_id.in_(prev_run_ids),
            Company.qualification != "disqualified",
        )
    )
    prev_companies = prev_companies_result.scalars().all()

    if not prev_companies:
        return []

    # Deduplicate against current discovery set
    carried = []
    seen_domains = set(current_domains)
    seen_names = set(current_names)

    for c in prev_companies:
        domain_norm = _normalize_domain(c.website) if c.website else ""
        name_norm = _normalize_company_name(c.name) if c.name else ""

        # Skip if already in current discovery set
        if domain_norm and domain_norm in seen_domains:
            continue
        if name_norm and name_norm in seen_names:
            continue

        # Mark as seen
        if domain_norm:
            seen_domains.add(domain_norm)
        if name_norm:
            seen_names.add(name_norm)

        carried.append({
            "name": c.name,
            "website": c.website,
            "industry": c.industry,
            "sub_industry": c.sub_industry,
            "city": c.city,
            "state_region": c.state_region,
            "country": c.country,
            "employee_count": c.employee_count,
            "revenue_estimate": c.revenue_estimate,
            "asset_value": c.asset_value,
            "description": c.description,
            "source": "carried_forward",
            "carried_forward": True,
        })

    logger.info(
        f"Carrying forward {len(carried)} companies from {len(prev_run_ids)} previous runs "
        f"(out of {len(prev_companies)} non-disqualified candidates)"
    )
    return carried


def apply_signal_result(db, company, signal_json, signal_type):
    """Apply signal research results to a single company (module-level).

    Parses agent JSON, sets budget/urgency scores, creates CompanyStageResult
    entries with evidence, and computes recency-adjusted scores.
    """
    from app.agent.lead_gen_agent import compute_recency_adjusted_scores

    if signal_type in ("budget_signals", "both"):
        budget_score = signal_json.get("budget_signal_score") or signal_json.get("composite_score", 0)
        company.budget_signal_score = _normalize_score_to_100(float(budget_score) if budget_score else None)

    if signal_type in ("urgency_signals", "both"):
        urgency_score = signal_json.get("urgency_signal_score") or signal_json.get("composite_score", 0)
        company.urgency_signal_score = _normalize_score_to_100(float(urgency_score) if urgency_score else None)

    signals_data = signal_json.get("signals", [])

    if signal_type in ("budget_signals", "both"):
        budget_signals = [s for s in signals_data if s.get("type") == "budget"] if signal_type == "both" else signals_data
        stage_result = CompanyStageResult(
            company_id=company.id,
            stage="budget_signals",
            status="passed",
            score=company.budget_signal_score,
            reasoning=f"Budget signal score: {company.budget_signal_score}/100",
            evidence=budget_signals[:10] if budget_signals else None,
        )
        db.add(stage_result)

    if signal_type in ("urgency_signals", "both"):
        urgency_signals = [s for s in signals_data if s.get("type") == "urgency"] if signal_type == "both" else signals_data
        stage_result = CompanyStageResult(
            company_id=company.id,
            stage="urgency_signals",
            status="passed",
            score=company.urgency_signal_score,
            reasoning=f"Urgency signal score: {company.urgency_signal_score}/100",
            evidence=urgency_signals[:10] if urgency_signals else None,
        )
        db.add(stage_result)

    if signal_type == "both":
        company.current_stage = "budget_urgency_signals"
    else:
        company.current_stage = signal_type

    # Compute recency-adjusted scores from evidence
    all_signals = signal_json.get("signals", [])
    recency_result = compute_recency_adjusted_scores(all_signals)
    if recency_result["recency_adjusted_budget_score"] is not None:
        company.recency_adjusted_budget_score = recency_result["recency_adjusted_budget_score"]
    if recency_result["recency_adjusted_urgency_score"] is not None:
        company.recency_adjusted_urgency_score = recency_result["recency_adjusted_urgency_score"]
    if recency_result["avg_evidence_age_months"] is not None:
        company.avg_evidence_age_months = recency_result["avg_evidence_age_months"]


def _deduplicate_contacts(contacts: list[dict]) -> list[dict]:
    """Deduplicate contacts by LinkedIn URL, email, and normalized name.

    When duplicates are found, merge data from all instances (take the richer record
    and fill in missing fields from duplicates).
    """
    result: list[dict] = []
    linkedin_index: dict[str, int] = {}   # linkedin_url -> result index
    email_index: dict[str, int] = {}      # email -> result index
    name_index: dict[str, int] = {}       # normalized name -> result index

    def _contact_richness(c: dict) -> int:
        """Score contact by number of useful fields."""
        score = 0
        if c.get("email"): score += 3
        if c.get("phone"): score += 3
        if c.get("linkedin_url"): score += 2
        if c.get("full_name"): score += 1
        if c.get("designation"): score += 1
        if c.get("source"): score += 1
        return score

    def _merge_contact(target: dict, source: dict):
        """Merge non-null fields from source into target."""
        for k, v in source.items():
            if v is not None and v != "" and not target.get(k):
                target[k] = v
        # Take higher confidence
        src_conf = source.get("confidence") or 0
        tgt_conf = target.get("confidence") or 0
        if src_conf > tgt_conf:
            target["confidence"] = src_conf

    def _normalize_name(name: str) -> str:
        """Normalize a person name for dedup."""
        # Remove middle initials, periods, extra whitespace
        n = re.sub(r"\b[A-Z]\.\s*", "", name.strip())
        n = re.sub(r"\s+", " ", n).strip().lower()
        return n

    for contact in contacts:
        linkedin = (contact.get("linkedin_url") or "").lower().strip().rstrip("/")
        email = (contact.get("email") or "").lower().strip()
        name = contact.get("full_name") or ""
        name_norm = _normalize_name(name) if name else ""

        # Layer 1: LinkedIn URL match
        if linkedin and linkedin in linkedin_index:
            idx = linkedin_index[linkedin]
            _merge_contact(result[idx], contact)
            if email:
                email_index[email] = idx
            continue

        # Layer 2: Email match
        if email and email in email_index:
            idx = email_index[email]
            _merge_contact(result[idx], contact)
            if linkedin:
                linkedin_index[linkedin] = idx
            continue

        # Layer 3: Name match (same name at same company)
        if name_norm and name_norm in name_index:
            idx = name_index[name_norm]
            existing = result[idx]
            if _contact_richness(contact) > _contact_richness(existing):
                _merge_contact(contact, existing)
                result[idx] = contact
            else:
                _merge_contact(existing, contact)
            if linkedin:
                linkedin_index[linkedin] = idx
            if email:
                email_index[email] = idx
            continue

        # No match — add as new
        idx = len(result)
        result.append(contact)
        if linkedin:
            linkedin_index[linkedin] = idx
        if email:
            email_index[email] = idx
        if name_norm:
            name_index[name_norm] = idx

    if len(contacts) != len(result):
        logger.info(f"Contact dedup: {len(contacts)} → {len(result)} unique contacts")
    return result


# ──────────────────────────────────────────────────────────────────
# Data reuse / caching
# ──────────────────────────────────────────────────────────────────

async def find_cached_company(domain: str, db, max_age_days: int = 30) -> Company | None:
    """Find the most recent, most enriched version of a company by domain.

    Only returns cached data that is less than max_age_days old (default 30 days).
    Stale data should be re-verified by the pipeline rather than blindly reused.
    """
    domain_clean = domain.lower().strip().removeprefix("www.").removeprefix("http://").removeprefix("https://").rstrip("/")
    if not domain_clean:
        return None

    cutoff = datetime.now(timezone.utc) - __import__('datetime').timedelta(days=max_age_days)

    result = await db.execute(
        select(Company)
        .where(func.lower(Company.website).contains(domain_clean))
        .where(Company.final_score.isnot(None))
        .where(Company.created_at >= cutoff)
        .order_by(Company.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def clone_company_data(cached: Company, new_company: Company):
    """Copy enriched data from a cached company to a new one."""
    if cached.employee_count and not new_company.employee_count:
        new_company.employee_count = cached.employee_count
    if cached.revenue_estimate and not new_company.revenue_estimate:
        new_company.revenue_estimate = cached.revenue_estimate
    if cached.asset_value and not new_company.asset_value:
        new_company.asset_value = cached.asset_value
    if cached.tech_stack_json and not new_company.tech_stack_json:
        new_company.tech_stack_json = cached.tech_stack_json
    if cached.description and not new_company.description:
        new_company.description = cached.description
    if cached.embedding is not None and new_company.embedding is None:
        new_company.embedding = cached.embedding

    new_company.cached_from_run_id = cached.pipeline_run_id
    new_company.data_freshness = cached.data_freshness or cached.created_at


# ──────────────────────────────────────────────────────────────────
# Firmographic pre-filter (computational — no agent)
# ──────────────────────────────────────────────────────────────────

def quick_firmographic_filter(companies: list[Company], icp: dict) -> tuple[list, list, list]:
    """Fast filter using data already available from Stage 1.

    Returns (passed, failed_with_reasons, needs_agent).

    Confidence tiers:
    - GREEN: Both metrics in range from reliable source → auto-pass
    - YELLOW: One metric known → needs agent verification
    - RED: Both known and both clearly outside range → auto-fail
    - GRAY: Both unknown → needs agent, capped at score 50
    """
    fd = icp.get("firmographic_details", {})
    emp_range = fd.get("employee_range", {})
    rev_range = fd.get("revenue_range", {})

    emp_min = emp_range.get("min")
    emp_max = emp_range.get("max")
    rev_min = rev_range.get("min")
    rev_max = rev_range.get("max")

    # Extract geography and industry keywords for pre-filtering
    geo = fd.get("geography", {})
    target_countries = {c.lower().strip() for c in geo.get("countries", [])}
    industry_keywords = set()
    for item in fd.get("industry_types", []):
        if isinstance(item, dict):
            v = (item.get("vertical") or "").lower().strip()
            sv = (item.get("sub_vertical") or "").lower().strip()
            if v:
                industry_keywords.add(v)
            if sv:
                industry_keywords.add(sv)
        elif isinstance(item, str):
            industry_keywords.add(item.lower().strip())

    passed = []
    failed = []
    needs_agent = []

    for c in companies:
        emp = c.employee_count
        rev = c.revenue_estimate

        # Geography pre-filter: if ICP specifies countries and company has a country,
        # check if it matches. Skip filter if no countries specified or company country unknown.
        if target_countries and c.country:
            company_country = c.country.lower().strip()
            if company_country and not any(
                tc in company_country or company_country in tc
                for tc in target_countries
            ):
                failed.append((c, f"Country '{c.country}' not in target geography: {', '.join(target_countries)}"))
                continue

        # Industry pre-filter: if company has an industry field, check if it overlaps
        # with any ICP industry keyword. Use substring matching for flexibility.
        if industry_keywords and c.industry:
            company_industry = c.industry.lower().strip()
            if company_industry and not any(
                kw in company_industry or company_industry in kw
                for kw in industry_keywords
            ):
                # Don't hard-fail — some companies have unusual industry labels.
                # Route to needs_agent instead for a second look.
                pass  # Industry mismatch is soft — let the agent decide

        emp_in_range = None  # None = unknown
        rev_in_range = None

        # Check employee range (tighter margins: 0.7x-1.5x)
        if emp and emp_min and emp_max:
            if emp < emp_min * 0.7 or emp > emp_max * 1.5:
                emp_in_range = False
            else:
                emp_in_range = True

        # Check revenue range (tighter margins: 0.5x-2x)
        if rev and rev_min and rev_max:
            if rev < rev_min * 0.5 or rev > rev_max * 2:
                rev_in_range = False
            else:
                rev_in_range = True

        # RED: Both known and both out of range → auto-fail
        if emp_in_range is False and rev_in_range is False:
            failed.append((c, f"Employee count {emp} and revenue ${rev:,} both outside range"))
            continue

        # RED: One known and clearly out of range, other also out or unknown
        if emp_in_range is False and rev_in_range is None:
            failed.append((c, f"Employee count {emp} outside range {emp_min}-{emp_max} (with 0.7x-1.5x margin)"))
            continue

        if rev_in_range is False and emp_in_range is None:
            failed.append((c, f"Revenue ${rev:,} outside range ${rev_min:,}-${rev_max:,} (with 0.5x-2x margin)"))
            continue

        # GREEN: Both known and both in range → auto-pass
        if emp_in_range is True and rev_in_range is True:
            passed.append(c)
            continue

        # GREEN: One in range, other unknown → pass (benefit of doubt)
        if (emp_in_range is True and rev_in_range is None) or (rev_in_range is True and emp_in_range is None):
            passed.append(c)
            continue

        # YELLOW: One in range but other out → needs agent to verify
        if (emp_in_range is True and rev_in_range is False) or (rev_in_range is True and emp_in_range is False):
            needs_agent.append(c)
            continue

        # GRAY: Both unknown → needs agent
        needs_agent.append(c)

    return passed, failed, needs_agent


# ──────────────────────────────────────────────────────────────────
# Shared error handling wrapper
# ──────────────────────────────────────────────────────────────────

async def _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, error, cancelled=False):
    """Shared error handling for pipeline execution failures."""
    try:
        await db.rollback()
    except Exception:
        pass

    try:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            if cancelled:
                run.status = "cancelled"
            else:
                run.status = "failed"
                run.error_log = f"{str(error)}\n{traceback.format_exc()}"
            run.completed_at = datetime.now(timezone.utc)

            for seq, event_data in enumerate(event_collector):
                log = PipelineLog(
                    pipeline_run_id=run_id,
                    event_type=event_data.get("type", "unknown"),
                    event_data=event_data,
                    sequence_number=seq,
                )
                db.add(log)
            await db.commit()
    except Exception as commit_err:
        logger.error(f"Failed to persist {'cancelled' if cancelled else 'error'} status for pipeline {run_id}: {commit_err}")

    if cancelled:
        await _emit_event(run_id_str, {
            "type": "cancelled",
            "companies_found": run.companies_found or 0 if run else 0,
            "contacts_found": run.contacts_found or 0 if run else 0,
        })
    else:
        await _emit_event(run_id_str, {
            "type": "error",
            "message": str(error),
        })


async def _persist_logs(db, run_id, event_collector, offset=0):
    """Persist event_collector to PipelineLog table."""
    for seq, event_data in enumerate(event_collector):
        log = PipelineLog(
            pipeline_run_id=run_id,
            event_type=event_data.get("type", "unknown"),
            event_data=event_data,
            sequence_number=offset + seq,
        )
        db.add(log)


async def _get_existing_log_count(db, run_id) -> int:
    """Count existing pipeline logs for sequence offset."""
    result = await db.execute(
        select(func.count(PipelineLog.id)).where(PipelineLog.pipeline_run_id == run_id)
    )
    return result.scalar() or 0


# ──────────────────────────────────────────────────────────────────
# Main pipeline: Stages 1 + 2 → pause for review
# ──────────────────────────────────────────────────────────────────

async def execute_pipeline(run_id: UUID):
    """Execute Stages 1 (Industry Discovery) and 2 (Firmographic Fit).

    After Stage 2 completes, the pipeline pauses for mandatory user review.
    The user selects companies and a signal_mode, then calls promote-firmographic.
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            logger.error(f"Pipeline run {run_id} not found")
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            logger.error(f"ICP config {run.icp_config_id} not found")
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            run.status = "running"
            run.current_stage = "industry_discovery"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            # ════════════════════════════════════════
            # STAGE 1: Industry Discovery
            # ════════════════════════════════════════
            logger.info(f"[Stage 1] Starting industry discovery for run {run_id}")
            await _emit_event(run_id_str, {
                "type": "stage_update",
                "stage": "industry_discovery",
                "progress": 5,
                "message": "Stage 1: Starting industry discovery...",
            })

            # ── Pre-seed: Embedding-powered discovery from past runs (C4)
            preseed_companies = []
            try:
                preseed_companies = await _preseed_from_embeddings(db, icp, run_id)
                if preseed_companies:
                    await _emit_event(run_id_str, {
                        "type": "stage_update",
                        "stage": "industry_discovery",
                        "progress": 7,
                        "message": f"Stage 1: Pre-seeded {len(preseed_companies)} companies from past runs...",
                    })
            except Exception as preseed_err:
                logger.warning(f"Embedding pre-seed failed (non-fatal): {preseed_err}")
                await db.rollback()
                # Re-fetch run and icp after rollback to reattach to session
                run_result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
                run = run_result.scalar_one()
                run.status = "running"
                run.current_stage = "industry_discovery"
                await db.commit()

            # ── Extract KB-known domains from pre-seeded companies
            kb_known_domains = []
            for c in preseed_companies:
                domain = (c.get("website") or "").strip()
                if domain:
                    d = _normalize_domain(domain)
                    if d and d not in kb_known_domains:
                        kb_known_domains.append(d)
            if kb_known_domains:
                logger.info(f"[Stage 1] {len(kb_known_domains)} KB-known domains passed to discovery agents")

            # ── Determine discovery mode
            discovery_mode = run.discovery_mode or "qlgen_only"
            sales_nav_url = run.sales_navigator_url

            # ── Evaboot extraction (Sales Navigator modes)
            evaboot_companies = []
            evaboot_credits_used = 0

            if discovery_mode in ("sales_navigator_only", "sales_navigator_plus_qlgen") and sales_nav_url:
                try:
                    from app.config import get_settings as _get_settings
                    max_credits = _get_settings().EVABOOT_MAX_CREDITS_PER_RUN

                    evaboot_companies, evaboot_credits_used = await _run_evaboot_extraction(
                        run_id_str=run_id_str,
                        sales_navigator_url=sales_nav_url,
                        event_collector=event_collector,
                        disabled_tools=disabled_tools,
                        max_credits=max_credits,
                    )

                    # Save Evaboot contacts for later use in Stage 4
                    # Store in stage_details so contact agent can check for existing contacts
                    evaboot_contacts_by_company = {}
                    for ec in evaboot_companies:
                        key = (ec.get("website") or ec.get("name", "")).lower().strip()
                        if key and ec.get("contacts"):
                            evaboot_contacts_by_company[key] = ec["contacts"]

                    # Track credits on the run
                    run.evaboot_credits_used = evaboot_credits_used
                    stage_details = run.stage_details or {}
                    stage_details["evaboot_extraction"] = {
                        "credits_used": evaboot_credits_used,
                        "prospects_found": sum(len(c.get("contacts", [])) for c in evaboot_companies),
                        "companies_found": len(evaboot_companies),
                    }
                    run.stage_details = stage_details
                    await db.commit()

                    logger.info(
                        f"[Stage 1] Evaboot extraction: {len(evaboot_companies)} companies, "
                        f"{evaboot_credits_used} credits used"
                    )
                except Exception as evaboot_err:
                    logger.error(f"[Stage 1] Evaboot extraction failed: {evaboot_err}")
                    if discovery_mode == "sales_navigator_only":
                        # Fatal — no other discovery sources
                        raise ValueError(f"Sales Navigator extraction failed: {evaboot_err}")
                    # For hybrid mode, log and continue with qlGen discovery
                    await _emit_event(run_id_str, {
                        "type": "stage_update",
                        "stage": "industry_discovery",
                        "progress": 8,
                        "message": f"Evaboot extraction failed ({evaboot_err}). Continuing with qlGen discovery...",
                    })

            # ── Standard qlGen discovery (qlgen_only or hybrid mode)
            discovered_sub1 = []
            discovered_sub2 = []

            if discovery_mode in ("qlgen_only", "sales_navigator_plus_qlgen"):
                # ── Sub-run 1: Structured data sources (local DB, APIs, Wikidata, OpenCorporates)
                await _emit_event(run_id_str, {
                    "type": "stage_update",
                    "stage": "industry_discovery",
                    "progress": 8 if not evaboot_companies else 22,
                    "message": "Stage 1a: Searching structured databases...",
                })

                callback_handler_1 = create_pipeline_callback_handler(
                    run_id_str, event_collector,
                    initial_stage="industry_discovery",
                )
                sub_agent_db = create_discovery_sub_agent_db(
                    callback_handler=callback_handler_1, disabled_tools=disabled_tools,
                )
                discovery_prompt = build_industry_discovery_prompt(icp, kb_known_domains=kb_known_domains or None)

                # Wire in cross-run discovery intelligence
                try:
                    fd = icp.get("firmographic_details", {})
                    industry_types = fd.get("industry_types", [])
                    intel_industry = ""
                    if industry_types and isinstance(industry_types[0], dict):
                        intel_industry = industry_types[0].get("vertical", "")
                    elif industry_types:
                        intel_industry = str(industry_types[0])
                    intel_countries = fd.get("geography", {}).get("countries", [])
                    intel_country = intel_countries[0] if intel_countries else ""
                    intelligence = await get_intelligence_for_icp(db, intel_industry, intel_country)
                    intel_text = format_intelligence_for_prompt(intelligence)
                    if intel_text:
                        discovery_prompt += "\n" + intel_text
                        logger.info(f"[Stage 1] Injected discovery intelligence for {intel_industry}/{intel_country}")
                except Exception as intel_err:
                    logger.debug(f"Discovery intelligence injection failed (non-fatal): {intel_err}")

                sub_result_1 = await asyncio.to_thread(sub_agent_db, discovery_prompt)
                sub_json_1 = parse_json_from_agent_result(sub_result_1)
                discovered_sub1_raw = sub_json_1.get("companies", [])
                discovered_sub1 = _soft_filter_discovered(discovered_sub1_raw, icp, "Stage 1a")
                logger.info(
                    f"[Stage 1a] Structured sources: agent output {len(discovered_sub1_raw)} companies, "
                    f"after soft filter {len(discovered_sub1)} kept"
                )

                # ── Sub-run 2: Web search discovery (DDG, Tavily, YC, scraping)
                await _emit_event(run_id_str, {
                    "type": "stage_update",
                    "stage": "industry_discovery",
                    "progress": 15 if not evaboot_companies else 23,
                    "message": f"Stage 1b: Web search discovery ({len(discovered_sub1)} already found)...",
                })

                callback_handler_2 = create_pipeline_callback_handler(
                    run_id_str, event_collector,
                    initial_stage="industry_discovery",
                )
                sub_agent_web = create_discovery_sub_agent_web(
                    callback_handler=callback_handler_2, disabled_tools=disabled_tools,
                )
                # Extract domains from sub-run 1 to help web sub-agent avoid duplicates
                # Note: KB domains are NOT included here — the carry-forward logic handles
                # historical company inclusion deterministically after discovery.
                known_domains = []
                for c in discovered_sub1:
                    domain = (c.get("website") or "").strip()
                    if domain:
                        d = _normalize_domain(domain)
                        if d and d not in known_domains:
                            known_domains.append(d)
                web_prompt = build_discovery_web_prompt(icp, already_found_count=len(discovered_sub1), known_domains=known_domains[:300])

                sub_result_2 = await asyncio.to_thread(sub_agent_web, web_prompt)
                sub_json_2 = parse_json_from_agent_result(sub_result_2)
                discovered_sub2_raw = sub_json_2.get("companies", [])
                discovered_sub2 = _soft_filter_discovered(discovered_sub2_raw, icp, "Stage 1b")
                logger.info(
                    f"[Stage 1b] Web search: agent output {len(discovered_sub2_raw)} companies, "
                    f"after soft filter {len(discovered_sub2)} kept"
                )

            # ── Sub-run 3: Gap Analysis & Similarity Expansion
            discovered_so_far = preseed_companies + evaboot_companies + discovered_sub1 + discovered_sub2

            # Analyze geographic coverage gaps (skip for sales_navigator_only — results are targeted)
            fd = icp.get("firmographic_details", {})
            target_countries = [c.lower().strip() for c in fd.get("geography", {}).get("countries", [])]
            gap_expansion_companies = []

            if discovery_mode != "sales_navigator_only" and target_countries and len(discovered_so_far) > 10:
                country_counts = {}
                for c in discovered_so_far:
                    country = (c.get("country") or "").lower().strip()
                    if country:
                        for tc in target_countries:
                            if tc in country or country in tc:
                                country_counts[tc] = country_counts.get(tc, 0) + 1
                                break

                # Identify underrepresented countries
                total = len(discovered_so_far)
                gaps = [c for c in target_countries if country_counts.get(c, 0) < total * 0.1]

                if gaps:
                    logger.info(f"[Stage 1c] Gap analysis: underrepresented countries: {gaps}")
                    await _emit_event(run_id_str, {
                        "type": "stage_update",
                        "stage": "industry_discovery",
                        "progress": 22,
                        "message": f"Stage 1c: Filling geographic gaps ({', '.join(gaps)})...",
                    })

                    # Run targeted Exa searches for each gap country
                    try:
                        from app.tools.exa_tool import exa_search as _exa_search_fn
                        kw = icp.get("firmographic_details", {}).get("industry_types", [])
                        industry_text = ""
                        for item in kw:
                            if isinstance(item, dict):
                                industry_text = item.get("vertical", "")
                                break
                            elif isinstance(item, str):
                                industry_text = item
                                break

                        for gap_country in gaps[:3]:
                            try:
                                result = _exa_search_fn(
                                    query=f"{industry_text} companies in {gap_country}",
                                    num_results=30,
                                    category="company",
                                )
                                if isinstance(result, dict):
                                    for r in result.get("results", []):
                                        gap_expansion_companies.append({
                                            "name": r.get("title", ""),
                                            "website": r.get("url", ""),
                                            "country": gap_country,
                                            "source": "exa_gap_fill",
                                            "description": (r.get("text") or "")[:300],
                                        })
                            except Exception as gap_err:
                                logger.debug(f"Gap fill for {gap_country} failed: {gap_err}")
                    except Exception as gap_outer_err:
                        logger.debug(f"Gap analysis failed (non-fatal): {gap_outer_err}")

                    if gap_expansion_companies:
                        logger.info(f"[Stage 1c] Gap fill: {len(gap_expansion_companies)} additional companies")

            # ── Merge all sub-runs
            discovered_raw = discovered_so_far + gap_expansion_companies
            logger.info(f"[Stage 1] Total discovered: {len(discovered_raw)} companies (raw, incl. {len(preseed_companies)} pre-seeded, {len(gap_expansion_companies)} gap-fill)")

            # Validate company data
            discovered_validated = validate_stage_companies(discovered_raw)
            logger.info(f"[Stage 1] After validation: {len(discovered_validated)} companies")

            if not discovered_validated:
                raise ValueError("Stage 1 discovery returned no valid companies")

            # Multi-layer deduplication: domain + name normalization + fuzzy matching
            unique_companies = _deduplicate_companies(discovered_validated)

            # Carry forward non-disqualified companies from previous runs of this ICP
            current_domains = {_normalize_domain(c.get("website", "")) for c in unique_companies if c.get("website")}
            current_names = {_normalize_company_name(c.get("name", "")) for c in unique_companies if c.get("name")}

            carried_forward = await _carry_forward_from_previous_runs(
                db, run.icp_config_id, run.user_id, run_id, current_domains, current_names,
            )
            carried_forward_count = len(carried_forward)
            if carried_forward:
                unique_companies = _deduplicate_companies(unique_companies + carried_forward)
                await _emit_event(run_id_str, {
                    "type": "stage_update",
                    "stage": "industry_discovery",
                    "progress": 24,
                    "message": f"Carried forward {carried_forward_count} companies from previous runs...",
                })

            # Save all discovered companies to DB
            companies_saved = 0
            for disc in unique_companies:
                # Compute revenue_estimate from min/max if not directly available
                disc_revenue = _safe_int(disc.get("revenue_estimate"))
                if not disc_revenue and (disc.get("revenue_min") or disc.get("revenue_max")):
                    rmin = disc.get("revenue_min")
                    rmax = disc.get("revenue_max")
                    if rmin and rmax:
                        disc_revenue = int((rmin + rmax) / 2)
                    else:
                        disc_revenue = rmin or rmax

                company = Company(
                    pipeline_run_id=run_id,
                    name=disc.get("name", "Unknown"),
                    website=disc.get("website"),
                    industry=disc.get("industry"),
                    sub_industry=disc.get("sub_industry"),
                    city=disc.get("city"),
                    state_region=disc.get("state") or disc.get("state_region"),
                    country=disc.get("country"),
                    employee_count=_safe_int(disc.get("employee_count")),
                    revenue_estimate=disc_revenue,
                    asset_value=_safe_int(disc.get("asset_value")),
                    description=disc.get("description"),
                    source=_safe_str(disc.get("source")),
                    current_stage="industry_discovery",
                    carried_forward=disc.get("carried_forward", False),
                    # Evaboot / LinkedIn enrichment fields
                    domain=disc.get("domain"),
                    linkedin_url=disc.get("linkedin_url"),
                    company_type=_safe_str(disc.get("company_type")),
                    year_founded=disc.get("year_founded"),
                    revenue_min=disc.get("revenue_min"),
                    revenue_max=disc.get("revenue_max"),
                    employee_growth_1y_pct=disc.get("employee_growth_1y_pct"),
                    funding_stage=_safe_str(disc.get("funding_stage")),
                    discovery_method=disc.get("discovery_method", "qlgen"),
                    headquarters_address=disc.get("headquarters_address"),
                    linkedin_data=disc.get("linkedin_data"),
                    raw_data_json=disc.get("raw_prospect_data"),
                )
                db.add(company)

                # Check knowledge base for enriched data
                if disc.get("website"):
                    from app.services.company_kb_service import lookup_from_kb, clone_from_kb
                    kb_record = await lookup_from_kb(disc["website"], db)
                    if kb_record:
                        clone_from_kb(kb_record, company)

                await db.flush()

                # Create stage result
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="industry_discovery",
                    status="passed",
                    reasoning=f"Discovered via {disc.get('source', 'unknown')}",
                )
                db.add(stage_result)

                # Save Evaboot contacts early (so Stage 4 can skip re-discovery)
                if disc.get("source") == "evaboot" and disc.get("contacts"):
                    for contact_data in disc["contacts"]:
                        contact = Contact(
                            company_id=company.id,
                            full_name=contact_data.get("full_name"),
                            first_name=contact_data.get("first_name"),
                            last_name=contact_data.get("last_name"),
                            designation=contact_data.get("designation"),
                            email=contact_data.get("email"),
                            phone=_safe_str(contact_data.get("phone")),
                            linkedin_url=contact_data.get("linkedin_url"),
                            source="evaboot",
                            confidence=0.8 if contact_data.get("email_validity") == "safe" else 0.5,
                            enrichment_status="enriched" if contact_data.get("email") else "pending",
                            raw_data_json=contact_data,
                        )
                        db.add(contact)

                companies_saved += 1

            await db.flush()

            await _emit_event(run_id_str, {
                "type": "stage_update",
                "stage": "industry_discovery",
                "progress": 25,
                "message": f"Stage 1 complete: {companies_saved} companies discovered. Starting firmographic fit check...",
            })

            # ════════════════════════════════════════
            # STAGE 2: Firmographic Fit
            # ════════════════════════════════════════
            run.current_stage = "firmographic_fit"
            await db.commit()

            logger.info(f"[Stage 2] Starting firmographic fit for run {run_id}")
            await _emit_event(run_id_str, {
                "type": "stage_update",
                "stage": "firmographic_fit",
                "progress": 30,
                "message": "Stage 2: Running firmographic fit check...",
            })

            # Fetch all discovered companies
            all_companies_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.current_stage == "industry_discovery",
                )
            )
            all_companies = list(all_companies_result.scalars().all())

            # ── Routing: split pre-qualified (LinkedIn Sales Navigator) vs standard ──
            pre_qualified = [c for c in all_companies if c.discovery_method == "linkedin_sales_navigator"]
            standard_companies = [c for c in all_companies if c.discovery_method != "linkedin_sales_navigator"]

            # Auto-qualify pre-filtered LinkedIn companies (skip Stage 2 agent)
            pre_qualified_count = 0
            for company in pre_qualified:
                company.current_stage = "firmographic_fit"
                company.qualification = "qualified"
                company.icp_match_score = company.icp_match_score or 80.0
                # Compute revenue_estimate from min/max if not set
                if not company.revenue_estimate and (company.revenue_min or company.revenue_max):
                    if company.revenue_min and company.revenue_max:
                        company.revenue_estimate = int((company.revenue_min + company.revenue_max) / 2)
                    else:
                        company.revenue_estimate = company.revenue_min or company.revenue_max
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="firmographic_fit",
                    status="skipped",
                    score=80.0,
                    reasoning="Pre-filtered via LinkedIn Sales Navigator. Firmographic fit assumed.",
                )
                db.add(stage_result)
                pre_qualified_count += 1

            if pre_qualified:
                await _emit_event(run_id_str, {
                    "type": "stage_update",
                    "stage": "firmographic_fit",
                    "progress": 32,
                    "message": f"{pre_qualified_count} Sales Navigator companies auto-qualified (Stage 2 skipped).",
                })

            # Pass 1: Computational pre-filter (only standard companies)
            if standard_companies:
                passed, failed, needs_agent = quick_firmographic_filter(standard_companies, icp)
            else:
                passed, failed, needs_agent = [], [], []

            # Save failed results
            for company, reason in failed:
                company.current_stage = "firmographic_fit"
                company.qualification = "disqualified"
                company.rejection_reason = reason
                stage_result = CompanyStageResult(
                    company_id=company.id,
                    stage="firmographic_fit",
                    status="failed",
                    reasoning=reason,
                )
                db.add(stage_result)

            logger.info(
                f"[Stage 2] Pre-filter: {len(passed)} passed, {len(failed)} failed, "
                f"{len(needs_agent)} need agent verification"
            )

            # Pass 2: Priority-based agent verification with variable batch sizes
            # GREEN (passed): batch size 15 — agent just confirms pre-existing data
            # YELLOW (needs_agent with some data): batch size 8 — moderate research
            # GRAY (needs_agent with no data): batch size 5 — full per-company research
            green_companies = sorted(passed, key=lambda c: compute_data_quality_score(c), reverse=True)
            yellow_companies = [c for c in needs_agent if c.employee_count or c.revenue_estimate]
            gray_companies = [c for c in needs_agent if not c.employee_count and not c.revenue_estimate]
            yellow_companies.sort(key=lambda c: compute_data_quality_score(c), reverse=True)
            gray_companies.sort(key=lambda c: compute_data_quality_score(c), reverse=True)

            prioritized_batches = []
            for batch in _chunk(green_companies, 15):
                prioritized_batches.append(batch)
            for batch in _chunk(yellow_companies, 8):
                prioritized_batches.append(batch)
            for batch in _chunk(gray_companies, 5):
                prioritized_batches.append(batch)

            logger.info(
                f"[Stage 2] Priority batching: {len(green_companies)} GREEN (batch=15), "
                f"{len(yellow_companies)} YELLOW (batch=8), {len(gray_companies)} GRAY (batch=5) "
                f"= {len(prioritized_batches)} total batches"
            )

            companies_passed = 0
            companies_failed_agent = 0

            for batch_idx, batch in enumerate(prioritized_batches):
                batch_dicts = []
                batch_map = {}
                for c in batch:
                    cdict = {
                        "name": c.name,
                        "website": c.website,
                        "industry": c.industry,
                        "sub_industry": c.sub_industry,
                        "country": c.country,
                        "employee_count": c.employee_count,
                        "revenue_estimate": c.revenue_estimate,
                        "description": (c.description or "")[:200],
                    }
                    if c.cached_from_run_id:
                        cdict["existing_data"] = True
                        cdict["data_freshness"] = str(c.data_freshness) if c.data_freshness else None
                    batch_dicts.append(cdict)
                    batch_map[(c.website or "").lower()] = c

                await _emit_event(run_id_str, {
                    "type": "stage_update",
                    "stage": "firmographic_fit",
                    "progress": 35 + int(25 * (batch_idx + 1) / max(len(prioritized_batches), 1)),
                    "message": f"Stage 2: Evaluating batch {batch_idx + 1} ({len(batch)} companies)...",
                })

                try:
                    fit_callback = create_pipeline_callback_handler(
                        run_id_str, event_collector,
                        initial_stage="firmographic_fit",
                    )
                    fit_agent = create_firmographic_fit_agent(
                        callback_handler=fit_callback, disabled_tools=disabled_tools,
                    )
                    fit_prompt = build_firmographic_fit_prompt(batch_dicts, icp)
                    fit_result = await asyncio.to_thread(fit_agent, fit_prompt)
                    fit_json = parse_json_from_agent_result(fit_result)

                    for evaluated in fit_json.get("companies", []):
                        domain = (evaluated.get("website") or "").lower()
                        company = batch_map.get(domain)
                        if not company:
                            # Try name match as fallback
                            for c in batch:
                                if c.name and c.name.lower() == (evaluated.get("name") or "").lower():
                                    company = c
                                    break
                        if not company:
                            continue

                        recommendation = evaluated.get("recommendation", "pass")
                        score = _normalize_score_to_100(evaluated.get("score", 50))
                        reasoning = evaluated.get("reasoning", "")

                        company.current_stage = "firmographic_fit"
                        company.icp_match_score = score

                        # Update employee/revenue/asset_value if agent found better data
                        if evaluated.get("employee_count"):
                            parsed = _safe_int(evaluated["employee_count"])
                            if parsed is not None:
                                company.employee_count = parsed
                        if evaluated.get("revenue_estimate"):
                            parsed = _safe_int(evaluated["revenue_estimate"])
                            if parsed is not None:
                                company.revenue_estimate = parsed
                        if evaluated.get("asset_value"):
                            parsed = _safe_int(evaluated["asset_value"])
                            if parsed is not None:
                                company.asset_value = parsed

                        if recommendation == "pass":
                            company.qualification = "qualified"
                            stage_result = CompanyStageResult(
                                company_id=company.id,
                                stage="firmographic_fit",
                                status="passed",
                                score=score,
                                reasoning=reasoning,
                                evidence=evaluated.get("per_criterion"),
                            )
                            companies_passed += 1
                        else:
                            company.qualification = "disqualified"
                            company.rejection_reason = reasoning
                            stage_result = CompanyStageResult(
                                company_id=company.id,
                                stage="firmographic_fit",
                                status="failed",
                                score=score,
                                reasoning=reasoning,
                                evidence=evaluated.get("per_criterion"),
                            )
                            companies_failed_agent += 1

                        db.add(stage_result)

                except PipelineCancelled:
                    raise
                except Exception as batch_err:
                    logger.warning(f"[Stage 2] Batch {batch_idx + 1} agent failed: {batch_err}. Marking as needs review.")
                    for c in batch:
                        if c.current_stage != "firmographic_fit":
                            c.current_stage = "firmographic_fit"
                            c.qualification = "qualified"
                            c.icp_match_score = 50  # Default middle score
                            stage_result = CompanyStageResult(
                                company_id=c.id,
                                stage="firmographic_fit",
                                status="passed",
                                score=50,
                                reasoning="Agent verification failed; defaulted to pass for user review",
                            )
                            db.add(stage_result)
                            companies_passed += 1

            await db.flush()

            # Update company counts
            run.companies_found = companies_saved

            # ════════════════════════════════════════
            # PAUSE: Mandatory user review
            # ════════════════════════════════════════
            await _persist_logs(db, run_id, event_collector)

            run.status = "awaiting_review"
            run.current_stage = "review_firmographic"
            run.stage_details = {
                "total_discovered": companies_saved,
                "newly_discovered": companies_saved - carried_forward_count,
                "carried_forward": carried_forward_count,
                "pre_qualified_sn": pre_qualified_count,
                "pre_filter_passed": len(passed),
                "pre_filter_failed": len(failed),
                "agent_passed": companies_passed,
                "agent_failed": companies_failed_agent,
            }
            await db.commit()

            # Record early intelligence (post-Stage 2) for future runs
            try:
                from app.services.intelligence_service import record_early_intelligence
                fd = icp.get("firmographic_details", {})
                industry_types = fd.get("industry_types", [])
                intel_industry = ""
                if industry_types and isinstance(industry_types[0], dict):
                    intel_industry = industry_types[0].get("vertical", "")
                elif industry_types:
                    intel_industry = str(industry_types[0])
                intel_countries = fd.get("geography", {}).get("countries", [])
                intel_country = intel_countries[0] if intel_countries else ""
                if not intel_industry:
                    logger.warning(f"Empty industry for early intelligence recording on run {run_id}")
                if not intel_country:
                    logger.warning(f"Empty country for early intelligence recording on run {run_id}")
                await record_early_intelligence(db, run_id, run.icp_config_id, intel_industry, intel_country)
                await db.commit()
            except Exception as intel_err:
                logger.warning(f"Early intelligence recording failed (non-fatal): {intel_err}")

            # Generate embeddings
            try:
                from app.services.embedding_service import embed_company
                company_results = await db.execute(
                    select(Company).where(Company.pipeline_run_id == run_id)
                )
                for comp in company_results.scalars().all():
                    if comp.embedding is None:
                        await embed_company(comp, db)
                await db.commit()
            except Exception as embed_err:
                logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

            total_failed = len(failed) + companies_failed_agent
            total_passed = companies_passed + pre_qualified_count
            await _emit_event(run_id_str, {
                "type": "awaiting_firmographic_review",
                "companies_passed": total_passed,
                "companies_failed": total_failed,
                "pre_qualified_sn": pre_qualified_count,
                "total": companies_saved,
            })

            logger.info(
                f"Pipeline {run_id} paused for firmographic review: "
                f"{total_passed} passed ({pre_qualified_count} pre-qualified SN), "
                f"{total_failed} failed out of {companies_saved}"
            )

        except PipelineCancelled:
            logger.info(f"Pipeline {run_id} cancelled by user")
            await event_store.clear_cancelled(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, None, cancelled=True)

        except Exception as e:
            logger.error(f"Pipeline {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Resume after firmographic review → Stage 3 signals
# ──────────────────────────────────────────────────────────────────

async def resume_after_firmographic(
    run_id: UUID,
    company_ids: list[UUID],
    signal_mode: str,
):
    """Resume pipeline after firmographic review. Runs signal research (Stage 3).

    signal_mode: "budget_first" | "urgency_first" | "both"
    """
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            # Mark selected companies as promoted, others as excluded
            all_companies_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.current_stage == "firmographic_fit",
                    Company.qualification != "disqualified",
                )
            )
            for company in all_companies_result.scalars().all():
                if company.id in company_ids:
                    company.promoted = True
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage="firmographic_fit",
                        status="promoted",
                        user_override=True,
                    )
                    db.add(stage_result)
                else:
                    company.promoted = False
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage="firmographic_fit",
                        status="excluded",
                        user_override=False,
                        reasoning="User deselected at firmographic review",
                    )
                    db.add(stage_result)

            run.signal_mode = signal_mode
            run.status = "running"
            await db.commit()

            # Fetch promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = list(promoted_result.scalars().all())

            if not promoted_companies:
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                await _emit_event(run_id_str, {"type": "completed", "companies_found": 0, "contacts_found": 0})
                return

            log_offset = await _get_existing_log_count(db, run_id)

            if signal_mode == "both":
                # Run BOTH budget + urgency signals in one pass
                run.current_stage = "budget_urgency_signals"
                await db.commit()

                await _run_signal_research(
                    db, run, promoted_companies, icp, "both",
                    run_id_str, event_collector, disabled_tools,
                )

                await _persist_logs(db, run_id, event_collector, offset=log_offset)
                run.status = "awaiting_review"
                run.current_stage = "review_signals"
                await db.commit()

                avg_budget = sum(c.budget_signal_score or 0 for c in promoted_companies) / max(len(promoted_companies), 1)
                avg_urgency = sum(c.urgency_signal_score or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

                await _emit_event(run_id_str, {
                    "type": "awaiting_signal_review",
                    "companies_scored": len(promoted_companies),
                    "avg_budget": round(avg_budget, 1),
                    "avg_urgency": round(avg_urgency, 1),
                })

            else:
                # Serial mode: run first signal type only
                first_type = "budget_signals" if signal_mode == "budget_first" else "urgency_signals"
                run.current_stage = first_type
                await db.commit()

                await _run_signal_research(
                    db, run, promoted_companies, icp, first_type,
                    run_id_str, event_collector, disabled_tools,
                )

                await _persist_logs(db, run_id, event_collector, offset=log_offset)
                run.signal_phase = "first_signal_done"
                run.status = "awaiting_review"
                run.current_stage = f"review_{first_type}"
                await db.commit()

                score_attr = "budget_signal_score" if first_type == "budget_signals" else "urgency_signal_score"
                avg_score = sum(getattr(c, score_attr) or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

                await _emit_event(run_id_str, {
                    "type": "awaiting_first_signal_review",
                    "signal_type": first_type,
                    "companies_scored": len(promoted_companies),
                    "avg_score": round(avg_score, 1),
                })

        except PipelineCancelled:
            await event_store.clear_cancelled(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, None, cancelled=True)
        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Resume after first signal review (serial mode only)
# ──────────────────────────────────────────────────────────────────

async def resume_after_first_signal(
    run_id: UUID,
    company_ids: list[UUID],
):
    """Resume after reviewing first signal results in serial mode.
    Runs the second signal type."""
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            # Mark selections
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            for company in promoted_result.scalars().all():
                if company.id not in company_ids:
                    company.promoted = False
                    first_type = "budget_signals" if run.signal_mode == "budget_first" else "urgency_signals"
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage=first_type,
                        status="excluded",
                        user_override=False,
                        reasoning=f"User deselected after {first_type.replace('_', ' ')} review",
                    )
                    db.add(stage_result)

            # Determine second signal type
            second_type = "urgency_signals" if run.signal_mode == "budget_first" else "budget_signals"

            run.status = "running"
            run.current_stage = second_type
            await db.commit()

            # Fetch still-promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = list(promoted_result.scalars().all())

            if not promoted_companies:
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                await _emit_event(run_id_str, {"type": "completed", "companies_found": 0, "contacts_found": 0})
                return

            log_offset = await _get_existing_log_count(db, run_id)

            await _run_signal_research(
                db, run, promoted_companies, icp, second_type,
                run_id_str, event_collector, disabled_tools,
            )

            await _persist_logs(db, run_id, event_collector, offset=log_offset)
            run.signal_phase = "second_signal_done"
            run.status = "awaiting_review"
            run.current_stage = f"review_{second_type}"
            await db.commit()

            score_attr = "budget_signal_score" if second_type == "budget_signals" else "urgency_signal_score"
            avg_score = sum(getattr(c, score_attr) or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

            await _emit_event(run_id_str, {
                "type": "awaiting_second_signal_review",
                "signal_type": second_type,
                "companies_scored": len(promoted_companies),
                "avg_score": round(avg_score, 1),
            })

        except PipelineCancelled:
            await event_store.clear_cancelled(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, None, cancelled=True)
        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Resume after final signal review → Stages 4 + 5
# ──────────────────────────────────────────────────────────────────

async def resume_after_signals(
    run_id: UUID,
    company_ids: list[UUID],
):
    """Resume after final signal review. Runs Stages 4 (contacts) + 5 (scoring)."""
    run_id_str = str(run_id)

    async with async_session() as db:
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            return

        icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
        icp_config = icp_result.scalar_one_or_none()
        if not icp_config:
            return

        icp = icp_config.config_json
        event_collector = []

        try:
            disabled_tools = await get_disabled_tool_names(db)
        except Exception:
            disabled_tools = set()

        try:
            # Mark final selections
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            for company in promoted_result.scalars().all():
                if company.id not in company_ids:
                    company.promoted = False

            run.status = "running"
            run.current_stage = "contact_discovery"
            await db.commit()

            # Fetch final promoted companies
            promoted_result = await db.execute(
                select(Company).where(
                    Company.pipeline_run_id == run_id,
                    Company.promoted == True,
                )
            )
            promoted_companies = list(promoted_result.scalars().all())

            if not promoted_companies:
                run.status = "completed"
                run.current_stage = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                await _emit_event(run_id_str, {"type": "completed", "companies_found": 0, "contacts_found": 0})
                return

            total_companies = len(promoted_companies)
            log_offset = await _get_existing_log_count(db, run_id)

            # ════════════════════════════════════════
            # STAGE 4: Contact Discovery
            # ════════════════════════════════════════
            await _emit_event(run_id_str, {
                "type": "stage_update",
                "stage": "contact_discovery",
                "progress": 60,
                "message": f"Stage 4: Finding contacts for {total_companies} companies...",
            })

            contacts_total = 0
            CONTACT_PARALLEL_BATCH = 5

            async def _process_contact_company(company, index):
                """Process a single company's contact discovery."""
                nonlocal contacts_total

                await _emit_event(run_id_str, {
                    "type": "company_start",
                    "company_name": company.name,
                    "company_index": index + 1,
                    "total_companies": total_companies,
                    "stage": "contact_discovery",
                    "progress": 60 + int(25 * (index + 1) / total_companies),
                })

                try:
                    # Get cached contacts if any
                    cached_contacts = None
                    if company.cached_from_run_id:
                        cached_result = await db.execute(
                            select(Contact).where(Contact.company_id == company.id)
                        )
                        existing = cached_result.scalars().all()
                        if existing:
                            cached_contacts = [
                                {
                                    "full_name": c.full_name,
                                    "designation": c.designation,
                                    "email": c.email,
                                    "linkedin_url": c.linkedin_url,
                                    "source": c.source,
                                }
                                for c in existing
                            ]

                    contact_callback = create_pipeline_callback_handler(
                        run_id_str, event_collector,
                        initial_stage="contact_discovery",
                    )
                    contact_agent = create_contact_agent(
                        callback_handler=contact_callback, disabled_tools=disabled_tools,
                    )

                    company_dict = {
                        "name": company.name,
                        "website": company.website,
                        "industry": company.industry,
                        "employee_count": company.employee_count,
                    }
                    contact_prompt = build_contact_discovery_prompt(company_dict, icp, cached_contacts)

                    contact_result = await asyncio.to_thread(contact_agent, contact_prompt)
                    contact_json = parse_json_from_agent_result(contact_result)

                    contacts_saved = 0
                    raw_contacts = contact_json.get("contacts", [])
                    validated_contacts = validate_stage_contacts(
                        raw_contacts, company.website or ""
                    )
                    # Deduplicate contacts before saving
                    validated_contacts = _deduplicate_contacts(validated_contacts)
                    for cd in validated_contacts:
                        contact = Contact(
                            company_id=company.id,
                            full_name=cd.get("full_name"),
                            first_name=cd.get("first_name"),
                            last_name=cd.get("last_name"),
                            designation=cd.get("designation"),
                            role_category=_safe_str(cd.get("role_category")),
                            email=cd.get("email"),
                            phone=_safe_str(cd.get("phone")),
                            linkedin_url=cd.get("linkedin_url"),
                            source=_safe_str(cd.get("source")),
                            confidence=cd.get("confidence"),
                            enrichment_status=cd.get("enrichment_status", "pending"),
                        )
                        db.add(contact)
                        contacts_saved += 1

                    company.current_stage = "contact_discovery"
                    stage_result = CompanyStageResult(
                        company_id=company.id,
                        stage="contact_discovery",
                        status="passed" if contacts_saved > 0 else "skipped",
                        score=float(contacts_saved),
                        reasoning=f"Found {contacts_saved} contacts",
                    )
                    db.add(stage_result)
                    contacts_total += contacts_saved

                    await _emit_event(run_id_str, {
                        "type": "company_stage_result",
                        "company_name": company.name,
                        "stage": "contact_discovery",
                        "status": "passed" if contacts_saved > 0 else "skipped",
                        "score": contacts_saved,
                    })

                except PipelineCancelled:
                    raise
                except Exception as err:
                    logger.warning(f"[Stage 4] Contact discovery failed for {company.name}: {err}")
                    company.current_stage = "contact_discovery"

            # Process contacts in parallel batches
            for batch_start in range(0, total_companies, CONTACT_PARALLEL_BATCH):
                batch = promoted_companies[batch_start:batch_start + CONTACT_PARALLEL_BATCH]

                run.stage_details = {
                    **(run.stage_details or {}),
                    "current_company_index": batch_start + 1,
                    "total_companies_in_stage": total_companies,
                    "contacts_found_so_far": contacts_total,
                }
                await db.commit()

                tasks = [
                    _process_contact_company(company, batch_start + i)
                    for i, company in enumerate(batch)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                await db.flush()

            # Post-Stage-4: Server-side contact deduplication
            try:
                from app.services.contact_dedup_service import deduplicate_company_contacts
                total_deduped = 0
                for company in promoted_companies:
                    removed = await deduplicate_company_contacts(db, company.id)
                    total_deduped += removed
                if total_deduped > 0:
                    await db.commit()
                    logger.info(f"Contact dedup removed {total_deduped} duplicates across {len(promoted_companies)} companies")
            except Exception as dedup_err:
                logger.warning(f"Contact dedup failed (non-fatal): {dedup_err}")

            # ════════════════════════════════════════
            # STAGE 5: Final Scoring & Ranking
            # ════════════════════════════════════════
            run.current_stage = "final_scoring"
            await db.commit()

            await _emit_event(run_id_str, {
                "type": "stage_update",
                "stage": "final_scoring",
                "progress": 90,
                "message": "Stage 5: Computing final scores and ranking...",
            })

            # Re-fetch with contacts loaded
            from sqlalchemy.orm import selectinload
            promoted_result = await db.execute(
                select(Company)
                .where(Company.pipeline_run_id == run_id, Company.promoted == True)
                .options(selectinload(Company.contacts))
            )
            promoted_companies = list(promoted_result.scalars().unique().all())

            from app.agent.lead_gen_agent import compute_deal_hotness
            for company in promoted_companies:
                company.final_score = compute_final_score(company, icp=icp)
                hotness, tier = compute_deal_hotness(
                    company.budget_signal_score,
                    company.urgency_signal_score,
                    company.recency_adjusted_budget_score,
                    company.recency_adjusted_urgency_score,
                    company.avg_evidence_age_months,
                )
                company.deal_hotness_score = hotness
                company.deal_hotness_tier = tier
                company.current_stage = "final_scoring"
                company.data_freshness = datetime.now(timezone.utc)

            # Rank by blended final score (70%) + hotness (30%)
            ranked = sorted(
                promoted_companies,
                key=lambda c: (c.final_score or 0) * 0.7 + (c.deal_hotness_score or 0) * 0.3,
                reverse=True,
            )
            for i, c in enumerate(ranked):
                c.final_rank = i + 1

            # Persist logs
            await _persist_logs(db, run_id, event_collector, offset=log_offset)

            run.status = "completed"
            run.current_stage = "completed"
            run.contacts_found = contacts_total
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Generate embeddings
            try:
                from app.services.embedding_service import embed_company
                for comp in promoted_companies:
                    if comp.embedding is None:
                        await embed_company(comp, db)
                await db.commit()
            except Exception as embed_err:
                logger.warning(f"Embedding generation failed (non-fatal): {embed_err}")

            # Upsert scored companies into the Knowledge Base
            try:
                from app.services.company_kb_service import upsert_company_to_kb
                for company in promoted_companies:
                    await upsert_company_to_kb(
                        company,
                        list(company.contacts) if company.contacts else [],
                        run_id,
                        db,
                    )
                await db.commit()
                logger.info(f"KB upsert: {len(promoted_companies)} companies written to knowledge base")
            except Exception as kb_err:
                logger.warning(f"KB upsert failed (non-fatal): {kb_err}")

            # Record cross-run discovery intelligence
            try:
                from app.services.intelligence_service import record_discovery_intelligence
                fd = icp.get("firmographic_details", {})
                industry_types = fd.get("industry_types", [])
                industry_name = ""
                if industry_types and isinstance(industry_types[0], dict):
                    industry_name = industry_types[0].get("vertical", "")
                elif industry_types:
                    industry_name = str(industry_types[0])
                countries = fd.get("geography", {}).get("countries", [])
                country_name = countries[0] if countries else ""
                if not industry_name:
                    logger.warning(f"Empty industry for discovery intelligence recording on run {run_id}")
                if not country_name:
                    logger.warning(f"Empty country for discovery intelligence recording on run {run_id}")
                await record_discovery_intelligence(
                    db, run_id, run.icp_config_id,
                    industry=industry_name, country=country_name,
                )
                await db.commit()
            except Exception as intel_err:
                logger.warning(f"Discovery intelligence recording failed (non-fatal): {intel_err}")

            avg_final = sum(c.final_score or 0 for c in promoted_companies) / max(len(promoted_companies), 1)

            await _emit_event(run_id_str, {
                "type": "completed",
                "companies_found": len(promoted_companies),
                "contacts_found": contacts_total,
                "avg_final_score": round(avg_final, 1),
            })

            logger.info(
                f"Pipeline {run_id} completed: {len(promoted_companies)} companies, "
                f"{contacts_total} contacts, avg score {avg_final:.1f}"
            )

        except PipelineCancelled:
            await event_store.clear_cancelled(run_id_str)
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, None, cancelled=True)
        except Exception as e:
            logger.error(f"Pipeline resume {run_id} failed: {e}\n{traceback.format_exc()}")
            await _handle_pipeline_error(db, run_id, run, event_collector, run_id_str, e)


# ──────────────────────────────────────────────────────────────────
# Signal research helper (used by resume_after_firmographic and resume_after_first_signal)
# ──────────────────────────────────────────────────────────────────

async def _run_signal_research(
    db, run, companies, icp, signal_type,
    run_id_str, event_collector, disabled_tools,
):
    """Run signal research for a list of companies.

    Groups companies by industry (up to 5 per group) for batch processing.
    Companies in the same industry share signal research context (regulatory
    changes, market trends) reducing redundant tool calls by 50-70%.

    signal_type: "budget_signals", "urgency_signals", or "both"
    """
    stage_name = {
        "budget_signals": "Budget Signal Research",
        "urgency_signals": "Urgency Signal Research",
        "both": "Budget & Urgency Signal Research",
    }.get(signal_type, signal_type)

    await _emit_event(run_id_str, {
        "type": "stage_update",
        "stage": signal_type if signal_type != "both" else "budget_urgency_signals",
        "progress": 40,
        "message": f"Stage 3: {stage_name} for {len(companies)} companies...",
    })

    stage_label = signal_type if signal_type != "both" else "budget_urgency_signals"
    BATCH_GROUP_SIZE = 4  # Max companies per batch agent call

    # Group companies by industry for batch processing (C3)
    industry_groups: dict[str, list] = {}
    for company in companies:
        industry_key = (company.industry or "unknown").lower().strip()
        industry_groups.setdefault(industry_key, []).append(company)

    # Flatten into batches: keep same-industry companies together, max BATCH_GROUP_SIZE per batch
    batches = []
    for industry, group in industry_groups.items():
        for i in range(0, len(group), BATCH_GROUP_SIZE):
            batches.append(group[i:i + BATCH_GROUP_SIZE])

    logger.info(
        f"[Stage 3] Grouped {len(companies)} companies into {len(batches)} "
        f"industry batches across {len(industry_groups)} industries"
    )

    def _apply_signal_result_local(company, signal_json):
        """Delegate to module-level apply_signal_result."""
        apply_signal_result(db, company, signal_json, signal_type)

    async def _process_signal_batch(batch, batch_index):
        """Process a batch of companies (same industry) via a single agent call."""
        for i, company in enumerate(batch):
            await _emit_event(run_id_str, {
                "type": "company_start",
                "company_name": company.name,
                "company_index": batch_index + i + 1,
                "total_companies": len(companies),
                "stage": stage_label,
                "progress": 40 + int(20 * (batch_index + i + 1) / len(companies)),
            })

        try:
            signal_callback = create_pipeline_callback_handler(
                run_id_str, event_collector,
                initial_stage=stage_label,
            )
            agent = create_signal_agent(
                callback_handler=signal_callback, disabled_tools=disabled_tools,
            )

            if len(batch) == 1:
                # Single company — use standard prompt
                company = batch[0]
                company_dict = {
                    "name": company.name,
                    "website": company.website,
                    "description": company.description,
                    "employee_count": company.employee_count,
                    "revenue_estimate": company.revenue_estimate,
                    "cached_from_run_id": str(company.cached_from_run_id) if company.cached_from_run_id else None,
                    "data_freshness": str(company.data_freshness) if company.data_freshness else None,
                }
                prompt = build_signal_prompt(company_dict, icp, signal_type)
                result = await asyncio.to_thread(agent, prompt)
                signal_json = parse_json_from_agent_result(result)
                _apply_signal_result_local(company, signal_json)

                await _emit_event(run_id_str, {
                    "type": "company_stage_result",
                    "company_name": company.name,
                    "stage": signal_type,
                    "status": "passed",
                    "score": _normalize_score_to_100(signal_json.get("composite_score", 0)),
                })
            else:
                # Multiple companies — use batch prompt
                company_dicts = []
                for company in batch:
                    company_dicts.append({
                        "name": company.name,
                        "website": company.website,
                        "description": company.description,
                        "industry": company.industry,
                        "employee_count": company.employee_count,
                        "revenue_estimate": company.revenue_estimate,
                    })

                prompt = build_batch_signal_prompt(company_dicts, icp, signal_type)
                result = await asyncio.to_thread(agent, prompt)
                batch_json = parse_json_from_agent_result(result)

                # Parse batch results
                company_results = batch_json.get("companies", [])
                # Build lookup by name for matching
                result_by_name = {}
                for cr in company_results:
                    name = (cr.get("name") or "").lower().strip()
                    result_by_name[name] = cr

                for company in batch:
                    company_name_key = company.name.lower().strip()
                    signal_json = result_by_name.get(company_name_key)

                    if signal_json:
                        _apply_signal_result_local(company, signal_json)
                        await _emit_event(run_id_str, {
                            "type": "company_stage_result",
                            "company_name": company.name,
                            "stage": signal_type,
                            "status": "passed",
                            "score": _normalize_score_to_100(signal_json.get("composite_score", 0)),
                        })
                    else:
                        # Batch didn't include this company — mark with default
                        logger.warning(f"[Stage 3] Batch result missing for {company.name}, assigning default score")
                        if signal_type == "both":
                            company.current_stage = "budget_urgency_signals"
                        else:
                            company.current_stage = signal_type

        except PipelineCancelled:
            raise
        except Exception as err:
            logger.warning(f"[Stage 3] Signal batch failed for {[c.name for c in batch]}: {err}")
            for company in batch:
                if signal_type == "both":
                    company.current_stage = "budget_urgency_signals"
                else:
                    company.current_stage = signal_type

    # Process industry batches in parallel (3 concurrent batches)
    PARALLEL_BATCHES = 3
    processed = 0
    for parallel_start in range(0, len(batches), PARALLEL_BATCHES):
        parallel_group = batches[parallel_start:parallel_start + PARALLEL_BATCHES]

        run.stage_details = {
            **(run.stage_details or {}),
            "current_company_index": processed + 1,
            "total_companies_in_stage": len(companies),
        }
        await db.commit()

        tasks = [
            _process_signal_batch(batch, processed + sum(len(batches[j]) for j in range(parallel_start, parallel_start + k)))
            for k, batch in enumerate(parallel_group)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        await db.flush()
        processed += sum(len(b) for b in parallel_group)


# ═══════════════════════════════════════════════════════════════════════
# On-demand single-company discovery (signal & contact)
# ═══════════════════════════════════════════════════════════════════════

async def discover_signals_for_company(
    company_id: UUID,
    signal_type: str = "both",
) -> None:
    """Run on-demand signal research for a single company.

    Reuses the same agent, prompt, and scoring logic as the batch pipeline
    but operates independently on one company with its own SSE event stream.
    """
    event_key = f"signal_discovery:{company_id}"

    try:
        from app.agent.lead_gen_agent import (
            compute_deal_hotness,
            compute_final_score,
        )
        from sqlalchemy import delete as sa_delete
        from sqlalchemy.orm import selectinload
        async with async_session() as db:
            # Load company
            result = await db.execute(
                select(Company)
                .where(Company.id == company_id)
                .options(selectinload(Company.contacts), selectinload(Company.stage_results))
            )
            company = result.scalar_one_or_none()
            if not company:
                await event_store.push_event(event_key, {"type": "error", "message": "Company not found"})
                return

            # Load ICP config via pipeline run
            run_result = await db.execute(
                select(PipelineRun).where(PipelineRun.id == company.pipeline_run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run:
                await event_store.push_event(event_key, {"type": "error", "message": "Pipeline run not found"})
                return

            icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
            icp_config = icp_result.scalar_one_or_none()
            if not icp_config:
                await event_store.push_event(event_key, {"type": "error", "message": "ICP config not found"})
                return
            icp = icp_config.config_json

            await event_store.push_event(event_key, {
                "type": "stage_update",
                "stage": signal_type if signal_type != "both" else "budget_urgency_signals",
                "progress": 10,
                "message": f"Starting signal discovery for {company.name}...",
            })

            # Clear old stage results for re-run
            stages_to_clear = []
            if signal_type in ("budget_signals", "both"):
                stages_to_clear.append("budget_signals")
            if signal_type in ("urgency_signals", "both"):
                stages_to_clear.append("urgency_signals")
            if stages_to_clear:
                await db.execute(
                    sa_delete(CompanyStageResult)
                    .where(CompanyStageResult.company_id == company_id)
                    .where(CompanyStageResult.stage.in_(stages_to_clear))
                )

            # Create agent
            disabled_tools = await get_disabled_tool_names(db)
            event_collector = []
            signal_callback = create_pipeline_callback_handler(
                event_key, event_collector, initial_stage=signal_type,
            )
            agent = create_signal_agent(
                callback_handler=signal_callback, disabled_tools=disabled_tools,
            )

            # Build prompt and run
            company_dict = {
                "name": company.name,
                "website": company.website,
                "description": company.description,
                "employee_count": company.employee_count,
                "revenue_estimate": company.revenue_estimate,
                "cached_from_run_id": str(company.cached_from_run_id) if company.cached_from_run_id else None,
                "data_freshness": str(company.data_freshness) if company.data_freshness else None,
            }
            prompt = build_signal_prompt(company_dict, icp, signal_type)
            result = await asyncio.to_thread(agent, prompt)
            signal_json = parse_json_from_agent_result(result)

            # Apply results
            apply_signal_result(db, company, signal_json, signal_type)

            # Compute deal hotness and final score
            hotness, tier = compute_deal_hotness(
                company.budget_signal_score,
                company.urgency_signal_score,
                company.recency_adjusted_budget_score,
                company.recency_adjusted_urgency_score,
                company.avg_evidence_age_months,
            )
            company.deal_hotness_score = hotness
            company.deal_hotness_tier = tier
            company.final_score = compute_final_score(company, icp=icp)
            company.data_freshness = datetime.now(timezone.utc)

            await db.commit()

            await event_store.push_event(event_key, {
                "type": "completed",
                "company_name": company.name,
                "budget_signal_score": company.budget_signal_score,
                "urgency_signal_score": company.urgency_signal_score,
                "deal_hotness_score": company.deal_hotness_score,
                "deal_hotness_tier": company.deal_hotness_tier,
                "final_score": company.final_score,
            })

    except Exception as e:
        logger.error(f"Signal discovery for {company_id} failed: {e}\n{traceback.format_exc()}")
        await event_store.push_event(event_key, {
            "type": "error",
            "message": f"Signal discovery failed: {str(e)[:200]}",
        })


async def discover_contacts_for_company(company_id: UUID) -> None:
    """Run on-demand contact discovery for a single company.

    Reuses the same agent, prompt, validation, and dedup logic as the batch
    pipeline but operates independently on one company.
    """
    from sqlalchemy import delete as sa_delete
    from sqlalchemy.orm import selectinload
    from app.services.contact_dedup_service import deduplicate_company_contacts

    event_key = f"contact_discovery:{company_id}"

    try:
        async with async_session() as db:
            # Load company
            result = await db.execute(
                select(Company)
                .where(Company.id == company_id)
                .options(selectinload(Company.contacts))
            )
            company = result.scalar_one_or_none()
            if not company:
                await event_store.push_event(event_key, {"type": "error", "message": "Company not found"})
                return

            # Load ICP config
            run_result = await db.execute(
                select(PipelineRun).where(PipelineRun.id == company.pipeline_run_id)
            )
            run = run_result.scalar_one_or_none()
            if not run:
                await event_store.push_event(event_key, {"type": "error", "message": "Pipeline run not found"})
                return

            icp_result = await db.execute(select(ICPConfig).where(ICPConfig.id == run.icp_config_id))
            icp_config = icp_result.scalar_one_or_none()
            if not icp_config:
                await event_store.push_event(event_key, {"type": "error", "message": "ICP config not found"})
                return
            icp = icp_config.config_json

            await event_store.push_event(event_key, {
                "type": "stage_update",
                "stage": "contact_discovery",
                "progress": 10,
                "message": f"Starting contact discovery for {company.name}...",
            })

            # Gather existing contacts as cached_contacts for context
            cached_contacts = []
            for c in (company.contacts or []):
                cached_contacts.append({
                    "full_name": c.full_name,
                    "designation": c.designation,
                    "email": c.email,
                    "linkedin_url": c.linkedin_url,
                    "source": c.source,
                })

            # Delete old contacts
            await db.execute(
                sa_delete(Contact).where(Contact.company_id == company_id)
            )

            # Create agent
            disabled_tools = await get_disabled_tool_names(db)
            event_collector = []
            contact_callback = create_pipeline_callback_handler(
                event_key, event_collector, initial_stage="contact_discovery",
            )
            agent = create_contact_agent(
                callback_handler=contact_callback, disabled_tools=disabled_tools,
            )

            # Build prompt and run
            company_dict = {
                "name": company.name,
                "website": company.website,
                "industry": company.industry,
                "employee_count": company.employee_count,
            }
            prompt = build_contact_discovery_prompt(company_dict, icp, cached_contacts if cached_contacts else None)
            result = await asyncio.to_thread(agent, prompt)
            contact_json = parse_json_from_agent_result(result)

            # Extract and validate contacts
            raw_contacts = contact_json.get("contacts", [])
            validated_contacts = validate_stage_contacts(raw_contacts, company.website)
            validated_contacts = _deduplicate_contacts(validated_contacts)

            # Save contacts
            for cd in validated_contacts:
                contact = Contact(
                    company_id=company.id,
                    full_name=cd.get("full_name"),
                    first_name=cd.get("first_name"),
                    last_name=cd.get("last_name"),
                    designation=cd.get("designation"),
                    role_category=_safe_str(cd.get("role_category")),
                    email=cd.get("email"),
                    phone=_safe_str(cd.get("phone")),
                    linkedin_url=cd.get("linkedin_url"),
                    city=cd.get("city"),
                    source=_safe_str(cd.get("source")),
                    confidence=cd.get("confidence"),
                    enrichment_status=cd.get("enrichment_status", "pending"),
                )
                db.add(contact)

            await db.flush()

            # Post-save dedup
            try:
                await deduplicate_company_contacts(db, company.id)
            except Exception as dedup_err:
                logger.warning(f"Contact dedup failed (non-fatal): {dedup_err}")

            await db.commit()

            # Count final contacts
            count_result = await db.execute(
                select(func.count(Contact.id)).where(Contact.company_id == company_id)
            )
            final_count = count_result.scalar() or 0

            await event_store.push_event(event_key, {
                "type": "completed",
                "company_name": company.name,
                "contacts_found": final_count,
            })

    except Exception as e:
        logger.error(f"Contact discovery for {company_id} failed: {e}\n{traceback.format_exc()}")
        await event_store.push_event(event_key, {
            "type": "error",
            "message": f"Contact discovery failed: {str(e)[:200]}",
        })
