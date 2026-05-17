"""Company Research service.

Looks up basic firmographic data for a company using existing agent tools
(apollo_company_search, research_company) and fills in missing KB fields
like domain, industry, country, city, employee_count, revenue_estimate.
"""
import asyncio
import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge_base import CompanyKnowledgeBase

logger = logging.getLogger(__name__)


async def research_company_info(
    db: AsyncSession,
    company_kb_id: UUID,
) -> dict:
    """Research and fill in missing firmographic data for a company.

    Uses existing agent tools in order:
    1. apollo_company_search — structured firmographic database
    2. research_company — multi-source web research (DuckDuckGo, scraping, LinkedIn)

    Only overwrites fields that are currently empty.
    Returns dict with the updated company fields.
    """
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        return {"error": "Company not found"}

    company_name = kb.canonical_name or ""
    domain = kb.normalized_domain or ""

    if not company_name and not domain:
        return {"error": "No company name or domain to research"}

    researched: dict = {}

    # Method 1: Apollo company search (structured firmographic data)
    apollo_data = await _run_apollo_search(company_name, domain)
    if apollo_data:
        researched.update(apollo_data)

    # Method 2: Multi-source web research (if Apollo didn't fill everything)
    missing_fields = _get_missing_fields(kb, researched)
    if missing_fields:
        web_data = await _run_company_research(company_name, domain or researched.get("domain", ""))
        if web_data:
            for key, val in web_data.items():
                if key not in researched or not researched[key]:
                    researched[key] = val

    # Apply researched data to KB (only overwrite empty fields)
    updated_fields = {}
    field_map = {
        "domain": "normalized_domain",
        "industry": "industry",
        "sub_industry": "sub_industry",
        "country": "country",
        "city": "city",
        "state_region": "state_region",
        "employee_count": "employee_count",
        "revenue_estimate": "revenue_estimate",
        "description": "description",
        "tech_stack": "tech_stack_json",
    }

    for research_key, kb_field in field_map.items():
        current_val = getattr(kb, kb_field, None)
        new_val = researched.get(research_key)
        if new_val and not current_val:
            setattr(kb, kb_field, new_val)
            updated_fields[research_key] = new_val

    await db.flush()

    return {
        "company_kb_id": str(company_kb_id),
        "company_name": kb.canonical_name,
        "fields_updated": list(updated_fields.keys()),
        "updated_data": updated_fields,
        "current_data": {
            "domain": kb.normalized_domain,
            "industry": kb.industry,
            "sub_industry": kb.sub_industry,
            "country": kb.country,
            "city": kb.city,
            "state_region": kb.state_region,
            "employee_count": kb.employee_count,
            "revenue_estimate": kb.revenue_estimate,
            "description": kb.description,
            "tech_stack": kb.tech_stack_json,
        },
    }


def _get_missing_fields(kb: CompanyKnowledgeBase, researched: dict) -> list[str]:
    """Return list of field names still missing after initial research."""
    missing = []
    checks = {
        "domain": kb.normalized_domain or researched.get("domain"),
        "industry": kb.industry or researched.get("industry"),
        "country": kb.country or researched.get("country"),
        "employee_count": kb.employee_count or researched.get("employee_count"),
        "revenue_estimate": kb.revenue_estimate or researched.get("revenue_estimate"),
        "description": kb.description or researched.get("description"),
    }
    for field, val in checks.items():
        if not val:
            missing.append(field)
    return missing


# ──────────────────────────────────────────────────────────────────
# Tool wrappers
# ──────────────────────────────────────────────────────────────────


async def _run_apollo_search(name: str, domain: str) -> dict | None:
    """Use the apollo_company_search agent tool to find firmographic data."""
    try:
        from app.tools.apollo_tool import apollo_company_search

        # Apollo search by company name (returns structured org data)
        query = name or domain
        raw = await asyncio.to_thread(
            apollo_company_search,
            query=query,
            per_page=5,
        )

        if not raw or raw.get("error") or raw.get("rate_limited"):
            logger.info(f"Apollo search returned no usable data for '{query}'")
            return None

        orgs = raw.get("organizations", [])
        if not orgs:
            return None

        # Pick the best match: prefer domain match, then first result
        best = orgs[0]
        if domain:
            for org in orgs:
                org_domain = (org.get("website_url") or "").replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
                if org_domain == domain:
                    best = org
                    break

        return _parse_apollo_org(best)
    except Exception as e:
        logger.warning(f"Apollo company search tool failed: {e}")
        return None


async def _run_company_research(name: str, domain: str) -> dict | None:
    """Use the research_company agent tool for multi-source web research.

    This tool combines DuckDuckGo searches, website scraping (team/about pages),
    and LinkedIn profile searches to gather company data.
    """
    try:
        from app.tools.company_research_tool import research_company

        raw = await asyncio.to_thread(
            research_company,
            company_name=name,
            company_domain=domain,
        )

        if not raw or isinstance(raw, str):
            return None

        return _parse_research_result(raw, domain)
    except Exception as e:
        logger.warning(f"Company research tool failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# Result parsers
# ──────────────────────────────────────────────────────────────────


def _parse_apollo_org(org: dict) -> dict:
    """Parse an Apollo organization object into our standard format."""
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
    if org.get("state"):
        data["state_region"] = org["state"]

    emp = org.get("estimated_num_employees")
    if emp and isinstance(emp, (int, float)):
        data["employee_count"] = int(emp)

    revenue = org.get("annual_revenue")
    if revenue and isinstance(revenue, (int, float)):
        data["revenue_estimate"] = int(revenue)
    elif isinstance(revenue, str):
        parsed = _parse_revenue_string(revenue)
        if parsed:
            data["revenue_estimate"] = parsed

    desc = org.get("short_description")
    if desc:
        data["description"] = desc[:2000]

    return data


def _parse_research_result(raw: dict, existing_domain: str) -> dict:
    """Parse the research_company tool result into our standard format.

    The tool returns:
      company_domain, description, financials (revenue_signals, employee_signals),
      tech_signals, contacts, news
    """
    data: dict = {}

    # Domain
    rd = raw.get("company_domain", "")
    if rd and not existing_domain:
        data["domain"] = rd.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")

    # Description
    if raw.get("description"):
        data["description"] = raw["description"][:2000]

    # Tech stack from tech_signals
    tech = raw.get("tech_signals")
    if tech and isinstance(tech, list):
        data["tech_stack"] = tech[:30]

    # Employee count from employee_signals
    financials = raw.get("financials", {})
    emp_signals = financials.get("employee_signals", [])
    for sig in emp_signals:
        text = sig if isinstance(sig, str) else str(sig)
        emp_count = _extract_number_from_text(text, "employee")
        if emp_count and 1 < emp_count < 10_000_000:
            data["employee_count"] = emp_count
            break

    # Revenue from revenue_signals
    rev_signals = financials.get("revenue_signals", [])
    for sig in rev_signals:
        text = sig.get("text", "") if isinstance(sig, dict) else str(sig)
        title = sig.get("title", "") if isinstance(sig, dict) else ""
        combined = f"{title} {text}"
        rev = _extract_revenue_from_text(combined)
        if rev:
            data["revenue_estimate"] = rev
            break

    return data


def _parse_revenue_string(s: str) -> int | None:
    """Parse revenue strings like '$1M-$10M' into estimated int."""
    if not s:
        return None
    s = s.upper().replace(",", "").replace("$", "").strip()
    parts = re.split(r'[-–]', s)
    values = []
    for part in parts:
        part = part.strip()
        multiplier = 1
        if part.endswith("B"):
            multiplier = 1_000_000_000
            part = part[:-1]
        elif part.endswith("M"):
            multiplier = 1_000_000
            part = part[:-1]
        elif part.endswith("K"):
            multiplier = 1_000
            part = part[:-1]
        try:
            values.append(int(float(part) * multiplier))
        except ValueError:
            continue
    if values:
        return sum(values) // len(values)
    return None


def _extract_number_from_text(text: str, context: str) -> int | None:
    """Extract a number near a context keyword from text."""
    text_lower = text.lower()
    patterns = [
        r'(\d[\d,]+)\s*(?:employees?|staff|workers|people)',
        r'(?:employs?|has|with|about|approximately|~)\s*(\d[\d,]+)',
        r'(?:headcount|workforce|team)\s*(?:of|:)\s*(\d[\d,]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return int(match.group(1).replace(",", ""))
    # Last resort: just find numbers in the text
    numbers = re.findall(r'(\d[\d,]+)', text)
    for n in numbers:
        val = int(n.replace(",", ""))
        if 10 < val < 10_000_000:
            return val
    return None


def _extract_revenue_from_text(text: str) -> int | None:
    """Extract revenue from text like '$2.5 billion revenue'."""
    patterns = [
        r'\$\s*([\d,.]+)\s*(billion|million|B|M)',
        r'([\d,.]+)\s*(billion|million)\s*(?:USD|dollars?)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = float(match.group(1).replace(",", ""))
            unit = match.group(2).lower()
            if unit in ("billion", "b"):
                return int(amount * 1_000_000_000)
            elif unit in ("million", "m"):
                return int(amount * 1_000_000)
    return None
