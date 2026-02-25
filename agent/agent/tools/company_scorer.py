import json

import structlog
from strands import tool

logger = structlog.get_logger()


@tool
def bant_score(company_profile: dict, icp_profile: dict, bant_weights: dict) -> dict:
    """
    Score a company on the BANT framework against an ICP.
    This tool uses heuristic scoring based on available company data.

    Args:
        company_profile: Enriched company data
        icp_profile: The target ICP criteria
        bant_weights: Weight allocation for each BANT dimension

    Returns:
        BANT scores (0-10 per dimension) with reasoning and weighted total
    """
    reasoning_parts = []

    # Budget scoring
    budget = _score_budget(company_profile)
    reasoning_parts.append(f"Budget ({budget}/10): {_budget_reasoning(company_profile)}")

    # Authority scoring
    authority = _score_authority(company_profile)
    reasoning_parts.append(f"Authority ({authority}/10): {_authority_reasoning(company_profile)}")

    # Need scoring
    need = _score_need(company_profile, icp_profile)
    reasoning_parts.append(f"Need ({need}/10): {_need_reasoning(company_profile, icp_profile)}")

    # Timeline scoring
    timeline = _score_timeline(company_profile)
    reasoning_parts.append(f"Timeline ({timeline}/10): {_timeline_reasoning(company_profile)}")

    # Weighted total
    w = bant_weights
    total = (
        budget * w.get("budget", 0.25)
        + authority * w.get("authority", 0.25)
        + need * w.get("need", 0.25)
        + timeline * w.get("timeline", 0.25)
    )
    total = round(min(10.0, max(0.0, total)), 2)

    reasoning = "\n".join(reasoning_parts)
    reasoning += f"\n\nWeighted Total: {total}/10 (B={w.get('budget', 0.25)}, A={w.get('authority', 0.25)}, N={w.get('need', 0.25)}, T={w.get('timeline', 0.25)})"

    result = {
        "budget": budget,
        "authority": authority,
        "need": need,
        "timeline": timeline,
        "total": total,
        "reasoning": reasoning,
    }

    logger.info(
        "bant_score completed",
        company=company_profile.get("company_name") or company_profile.get("organization") or company_profile.get("domain", "unknown"),
        total=total,
    )
    return result


def _score_budget(profile: dict) -> float:
    score = 3.0
    revenue = profile.get("estimated_revenue") or profile.get("annual_revenue") or profile.get("revenue")
    funding = profile.get("funding_stage", "")
    total_funding = profile.get("total_funding")

    if revenue:
        if revenue > 50_000_000:
            score = 9.0
        elif revenue > 10_000_000:
            score = 7.5
        elif revenue > 1_000_000:
            score = 6.0
        else:
            score = 4.0

    if funding:
        funding_lower = funding.lower()
        if any(s in funding_lower for s in ["series c", "series d", "ipo", "public"]):
            score = max(score, 9.0)
        elif any(s in funding_lower for s in ["series b"]):
            score = max(score, 8.0)
        elif any(s in funding_lower for s in ["series a"]):
            score = max(score, 6.5)

    if total_funding and total_funding > 10_000_000:
        score = max(score, 7.5)

    return min(10.0, score)


def _score_authority(profile: dict) -> float:
    score = 3.0
    emp = profile.get("employee_count")
    if emp:
        if emp > 500:
            score = 8.0
        elif emp > 100:
            score = 7.0
        elif emp > 20:
            score = 5.5
        else:
            score = 4.0

    if profile.get("linkedin_url"):
        score = min(10.0, score + 1.0)

    return min(10.0, score)


def _score_need(profile: dict, icp: dict) -> float:
    score = 3.0

    # Industry match
    profile_industry = (profile.get("industry") or "").lower()
    icp_industries = [i.lower() for i in (icp.get("industries") or [])]
    if any(ind in profile_industry for ind in icp_industries):
        score += 3.0

    # Tech stack match
    profile_tech = [t.lower() for t in (profile.get("tech_stack") or [])]
    icp_tech = [t.lower() for t in (icp.get("techStack") or icp.get("tech_stack") or [])]
    if profile_tech and icp_tech:
        matches = sum(1 for t in icp_tech if any(t in pt for pt in profile_tech))
        if matches > 0:
            score += min(4.0, matches * 1.5)

    return min(10.0, score)


def _score_timeline(profile: dict) -> float:
    score = 3.0
    funding = profile.get("funding_stage", "")

    if funding:
        score = max(score, 5.5)
        if any(s in funding.lower() for s in ["series", "seed", "round"]):
            score = max(score, 6.5)

    emp = profile.get("employee_count")
    if emp and emp > 50:
        score = max(score, 5.0)

    return min(10.0, score)


def _budget_reasoning(profile: dict) -> str:
    parts = []
    revenue = profile.get("estimated_revenue") or profile.get("annual_revenue") or profile.get("revenue")
    if revenue:
        parts.append(f"Estimated revenue: ${revenue:,}")
    funding = profile.get("funding_stage")
    if funding:
        parts.append(f"Funding stage: {funding}")
    total = profile.get("total_funding")
    if total:
        parts.append(f"Total funding: ${total:,}")
    return "; ".join(parts) if parts else "Limited financial data available"


def _authority_reasoning(profile: dict) -> str:
    parts = []
    emp = profile.get("employee_count")
    if emp:
        parts.append(f"{emp} employees")
    if profile.get("linkedin_url"):
        parts.append("LinkedIn presence confirmed")
    return "; ".join(parts) if parts else "Limited organizational data available"


def _need_reasoning(profile: dict, icp: dict) -> str:
    parts = []
    if profile.get("industry"):
        parts.append(f"Industry: {profile['industry']}")
    tech = profile.get("tech_stack")
    if tech:
        parts.append(f"Tech stack: {', '.join(tech[:5])}")
    return "; ".join(parts) if parts else "Limited alignment data available"


def _timeline_reasoning(profile: dict) -> str:
    parts = []
    funding = profile.get("funding_stage")
    if funding:
        parts.append(f"Funding stage: {funding}")
    emp = profile.get("employee_count")
    if emp:
        parts.append(f"Company size: {emp} (growth indicator)")
    return "; ".join(parts) if parts else "No urgency signals detected"
