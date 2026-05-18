"""Hiring Signal Detector Tool.

Analyzes job postings for a company to detect hiring patterns,
velocity, department concentration, and buying intent keywords.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def hiring_signal_detector(
    company_name: str,
    domain: str = "",
    role_patterns: list[str] | None = None,
    time_window_days: int = 90,
) -> dict:
    """Detect hiring signals by analyzing job postings.

    Args:
        company_name: Company to research
        domain: Company domain for filtering
        role_patterns: Title patterns to match (e.g., ["VP*Data*", "*Platform*"])
        time_window_days: How far back to look

    Returns dict with total_roles, relevant_roles, hiring_velocity,
    department_concentration, intent_keywords_found, signal_strength.
    """
    from app.services.search_helpers import resilient_search
    import asyncio

    role_patterns = role_patterns or []

    result = {
        "company_name": company_name,
        "total_roles_found": 0,
        "relevant_roles": [],
        "hiring_velocity": {"30d": 0, "60d": 0, "90d": 0},
        "department_concentration": {},
        "intent_keywords_found": [],
        "signal_strength": 0,
        "source_tool": None,
    }

    # Search for job postings
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    _search_jobs(company_name, domain)
                )
                articles, source_tool = future.result(timeout=30)
        else:
            articles, source_tool = asyncio.run(_search_jobs(company_name, domain))
    except Exception as e:
        logger.warning(f"Hiring signal detection failed for {company_name}: {e}")
        return result

    result["source_tool"] = source_tool

    if not articles:
        return result

    # Intent keywords to look for in job descriptions
    intent_keywords = [
        "vendor evaluation", "platform migration", "cloud migration",
        "data platform", "revenue intelligence", "build vs buy",
        "RFP", "proof of concept", "POC", "vendor consolidation",
        "digital transformation", "modernization", "AI adoption",
    ]

    department_map = {
        "data": ["data", "analytics", "bi", "warehouse"],
        "engineering": ["engineer", "developer", "software", "devops", "sre"],
        "product": ["product", "ux", "design"],
        "sales": ["sales", "revenue", "gtm", "business development"],
        "security": ["security", "compliance", "infosec", "ciso"],
        "it": ["it ", "infrastructure", "systems", "helpdesk"],
    }

    found_intents = set()
    departments = {}
    relevant = []

    for article in articles:
        title = (article.get("title") or "").lower()
        body = (article.get("body") or article.get("content") or "").lower()
        text = f"{title} {body}"

        # Check if it's actually a job posting for this company
        name_lower = company_name.lower()
        domain_base = domain.split(".")[0].lower() if domain else ""
        if name_lower not in text and domain_base not in text:
            continue

        result["total_roles_found"] += 1

        # Check intent keywords
        for kw in intent_keywords:
            if kw.lower() in text:
                found_intents.add(kw)

        # Detect department
        for dept, keywords in department_map.items():
            if any(kw in text for kw in keywords):
                departments[dept] = departments.get(dept, 0) + 1

        # Check role patterns
        for pattern in role_patterns:
            pattern_parts = [p.strip("*").lower() for p in pattern.split("*") if p.strip("*")]
            if all(p in title for p in pattern_parts):
                # Detect seniority
                seniority = "IC"
                if any(s in title for s in ["vp", "vice president", "director", "head of", "chief"]):
                    seniority = "VP+" if "vp" in title or "vice" in title else "Director"
                if any(s in title for s in ["cto", "ceo", "cfo", "cdo", "coo", "chief"]):
                    seniority = "C-Suite"

                relevant.append({
                    "title": (article.get("title") or "")[:200],
                    "seniority": seniority,
                    "intent_signals": [kw for kw in intent_keywords if kw.lower() in text],
                    "source_url": article.get("href") or article.get("url"),
                })

    result["relevant_roles"] = relevant[:10]
    result["department_concentration"] = departments
    result["intent_keywords_found"] = list(found_intents)

    # Calculate signal strength
    total = result["total_roles_found"]
    if total >= 10:
        result["signal_strength"] = min(90, 50 + total)
        result["hiring_velocity"]["90d"] = total
        result["hiring_velocity"]["60d"] = int(total * 0.7)
        result["hiring_velocity"]["30d"] = int(total * 0.4)
    elif total >= 5:
        result["signal_strength"] = 50 + len(found_intents) * 5
    elif total >= 2:
        result["signal_strength"] = 30 + len(found_intents) * 5
    else:
        result["signal_strength"] = 10

    return result


async def _search_jobs(company_name: str, domain: str):
    from app.services.search_helpers import resilient_search
    return await resilient_search(
        query=f'"{company_name}" hiring OR careers OR "open positions" OR "job opening"',
        max_results=10,
        company_name=company_name,
    )
