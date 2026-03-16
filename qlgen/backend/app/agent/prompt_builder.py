"""Prompt builders for the 5-stage pipeline.

Each builder constructs the user-facing prompt for one agent invocation,
injecting ICP criteria, cached data, and stage-specific context.
"""
import json
from datetime import datetime, timezone


# ──────────────────────────────────────────────────────────────────
# ICP formatting helpers
# ──────────────────────────────────────────────────────────────────

def _format_firmographic_section(icp: dict) -> str:
    """Format the firmographic_details section of the ICP."""
    fd = icp.get("firmographic_details", {})
    lines = []

    # Industry types
    industry_types = fd.get("industry_types", [])
    if industry_types:
        ind_lines = ["INDUSTRY TYPES:"]
        for item in industry_types:
            if isinstance(item, dict):
                v = item.get("vertical", "")
                sv = item.get("sub_vertical", "")
                ind_lines.append(f"  - {v} > {sv}" if sv else f"  - {v}")
            else:
                ind_lines.append(f"  - {item}")
        lines.append("\n".join(ind_lines))

    # Geography
    geo = fd.get("geography", {})
    countries = geo.get("countries", [])
    if countries:
        lines.append(f"GEOGRAPHY: {', '.join(countries)}")

    # Revenue range
    rev = fd.get("revenue_range", {})
    if rev:
        currency = rev.get("currency", "USD")
        lines.append(f"REVENUE RANGE: ${rev.get('min', 'N/A'):,} - ${rev.get('max', 'N/A'):,} {currency}")

    # Employee range
    emp = fd.get("employee_range", {})
    if emp:
        lines.append(f"EMPLOYEE RANGE: {emp.get('min', 'N/A')} - {emp.get('max', 'N/A')}")

    # Low cost center
    if fd.get("low_cost_center") is not None:
        lines.append(f"LOW-COST R&D CENTER: {'Required' if fd['low_cost_center'] else 'Not required'}")

    return "\n".join(lines)


def _format_capability_section(icp: dict) -> str:
    tc = icp.get("target_capability", {})
    offerings = tc.get("offerings", [])
    condition = tc.get("condition", "OR")
    if offerings:
        return f"TARGET CAPABILITY: {' {condition} '.join(offerings)}"
    return ""


def _format_urgency_section(icp: dict) -> str:
    us = icp.get("urgency_signals", {})
    signals = us.get("signals", [])
    condition = us.get("condition", "OR")
    if signals:
        header = f"URGENCY SIGNALS TO LOOK FOR (match condition: {condition} — company must show {'ALL' if condition == 'AND' else 'ANY'} of these):"
        return header + "\n" + "\n".join(f"  - {s}" for s in signals)
    return ""


def _format_budget_section(icp: dict) -> str:
    bs = icp.get("budget_signals", {})
    signals = bs.get("signals", [])
    condition = bs.get("condition", "OR")
    if signals:
        header = f"BUDGET SIGNALS TO LOOK FOR (match condition: {condition} — company must show {'ALL' if condition == 'AND' else 'ANY'} of these):"
        return header + "\n" + "\n".join(f"  - {s}" for s in signals)
    return ""


def _format_authority_section(icp: dict) -> str:
    ar = icp.get("authority_roles", {})
    roles = ar.get("target_roles", [])
    if roles:
        return f"TARGET ROLES: {', '.join(roles)}"
    return ""


def _format_full_icp(icp: dict) -> str:
    """Format all ICP sections into a readable block."""
    sections = [
        _format_firmographic_section(icp),
        _format_capability_section(icp),
        _format_urgency_section(icp),
        _format_budget_section(icp),
        _format_authority_section(icp),
    ]
    return "\n\n".join(s for s in sections if s)


def _extract_keywords(icp: dict) -> dict:
    """Extract structured keywords from ICP for tool queries."""
    fd = icp.get("firmographic_details", {})

    industry_keywords = []
    sub_verticals = []
    for item in fd.get("industry_types", []):
        if isinstance(item, dict):
            v = item.get("vertical", "")
            sv = item.get("sub_vertical", "")
            if v:
                industry_keywords.append(v)
            if sv:
                sub_verticals.append(sv)
        elif isinstance(item, str):
            industry_keywords.append(item)

    geo = fd.get("geography", {})
    regions = geo.get("countries", [])

    emp = fd.get("employee_range", {})
    rev = fd.get("revenue_range", {})

    tc = icp.get("target_capability", {})
    offerings = tc.get("offerings", [])

    ar = icp.get("authority_roles", {})
    target_roles = ar.get("target_roles", ["CEO", "CTO", "COO", "VP Engineering"])

    return {
        "industry_keywords": industry_keywords,
        "sub_verticals": sub_verticals,
        "regions": regions,
        "emp_min": emp.get("min"),
        "emp_max": emp.get("max"),
        "rev_min": rev.get("min"),
        "rev_max": rev.get("max"),
        "offerings": offerings,
        "target_roles": target_roles,
    }


# ──────────────────────────────────────────────────────────────────
# Stage 1: Industry Discovery
# ──────────────────────────────────────────────────────────────────

def build_industry_discovery_prompt(icp: dict) -> str:
    """Build prompt for Stage 1 — discover ALL companies matching industry + geography."""
    kw = _extract_keywords(icp)
    fd = icp.get("firmographic_details", {})

    industry_text = ", ".join(kw["industry_keywords"])
    sub_vert_text = ", ".join(kw["sub_verticals"]) if kw["sub_verticals"] else "N/A"
    regions_text = ", ".join(kw["regions"]) if kw["regions"] else "Global"

    return f"""Discover ALL companies matching the following industry, vertical, and geography criteria.
There is NO upper limit on company count — find as many as possible. Aim for atleast 500 companies
without breaking the search criteria.

INDUSTRY: {industry_text}
SUB-VERTICALS: {sub_vert_text}
GEOGRAPHY: {regions_text}

STEP 1 — LOCAL DATABASE:
Call search_local_companies with the industry and country filters.
This returns companies we already know about from previous searches. Include ALL matching results.

STEP 2 — TRAINING KNOWLEDGE:
List well-known companies in {industry_text} / {sub_vert_text} in {regions_text} from your training
knowledge. Include: major corporations, mid-market companies, notable startups, recently funded
companies. Be exhaustive — list every company you know.

STEP 3 — TOOL-BASED DISCOVERY:
Use ALL available tools aggressively to discover additional companies:
- apollo_company_search: PAGINATE heavily. Query variations by sub-vertical, region, keyword.
  Fetch pages 1, 2, 3, 4+ for each query. Make 10+ calls.
- exa_search: Run 8-12 different query angles. Vary keywords, regions, adjacent terms.
- discover_icp_companies: Use for broad DDG-based batch discovery. 2-3 calls.
- search_yc_companies: Check YC directory for startups in this vertical.
- tavily_search: Search for "top {industry_text} companies" lists, directories, rankings.
- duckduckgo_search: Search for industry directories, associations, conference exhibitor lists.
- scrape_webpage: Scrape industry directories and "top companies" lists found by other tools.

Do NOT filter by revenue, employee count, or tech stack at this stage. That happens in Stage 2.

OUTPUT FORMAT — Return JSON:
```json
{{
  "companies": [
    {{
      "name": "Company Name",
      "website": "domain.com",
      "industry": "Industry",
      "sub_industry": "Sub-industry",
      "country": "Country",
      "city": "City",
      "employee_count": 500,
      "revenue_estimate": 50000000,
      "asset_value": 75000000,
      "description": "Brief description",
      "source": "tool_name",
      "is_from_local_db": false
    }}
  ],
  "discovery_summary": {{
    "total_found": 150,
    "from_local_db": 12,
    "from_training_knowledge": 30,
    "from_tools": 108,
    "tools_used": {{"apollo_company_search": 12, "exa_search": 10}}
  }}
}}
```"""


# ──────────────────────────────────────────────────────────────────
# Stage 2: Firmographic Fit
# ──────────────────────────────────────────────────────────────────

def build_firmographic_fit_prompt(companies: list[dict], icp: dict) -> str:
    """Build prompt for Stage 2 agent — deep firmographic verification of a batch."""
    fd = icp.get("firmographic_details", {})
    emp = fd.get("employee_range", {})
    rev = fd.get("revenue_range", {})
    tc = icp.get("target_capability", {})

    companies_json = json.dumps(companies, indent=2, default=str)

    return f"""Evaluate EACH company in this batch against the firmographic criteria below.

═══════════════════════════════════════════
FIRMOGRAPHIC CRITERIA
═══════════════════════════════════════════
Revenue range: ${rev.get('min', 'N/A'):,} - ${rev.get('max', 'N/A'):,} {rev.get('currency', 'USD')}
Employee range: {emp.get('min', 'N/A')} - {emp.get('max', 'N/A')}
Target capability fit: Company should need {json.dumps(tc.get('offerings', []))}. Condition: {tc.get('condition', 'OR')}
Low-cost R&D center: {fd.get('low_cost_center', 'Not specified')}

═══════════════════════════════════════════
COMPANIES TO EVALUATE
═══════════════════════════════════════════
{companies_json}

═══════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════
If EXISTING DATA is provided for a company (from prior runs), VERIFY it is still current.
If data is <30 days old, trust it. If >90 days old, re-verify with tools.

Use tools (apollo_company_search, scrape_webpage, exa_search, duckduckgo_search) to fill
gaps in company data — especially missing employee counts and revenue estimates.

For EACH company output:
```json
{{
  "companies": [
    {{
      "name": "Company Name",
      "website": "domain.com",
      "recommendation": "pass",
      "score": 78,
      "employee_count": 350,
      "revenue_estimate": 45000000,
      "per_criterion": {{
        "revenue": {{"value": 45000000, "in_range": true, "source": "apollo"}},
        "employees": {{"value": 350, "in_range": true, "source": "apollo"}},
        "capability_fit": {{"match": true, "reasoning": "Develops medical devices, needs engineering services"}},
        "low_cost_center": {{"has_center": false, "source": "scrape_webpage"}}
      }},
      "reasoning": "Revenue $45M and 350 employees within range. Capability fit confirmed."
    }}
  ]
}}
```"""


# ──────────────────────────────────────────────────────────────────
# Stage 3: Signal Research (Budget / Urgency / Both)
# ──────────────────────────────────────────────────────────────────

def build_signal_prompt(company: dict, icp: dict, signal_type: str) -> str:
    """Build prompt for Stage 3 — budget and/or urgency signal research.

    Args:
        company: Company dict with existing data
        icp: Full ICP config
        signal_type: "budget_signals", "urgency_signals", or "both"
    """
    name = company.get("name", "Unknown")
    domain = company.get("website", "unknown")
    description = company.get("description", "")
    employee_count = company.get("employee_count", "Unknown")
    revenue = company.get("revenue_estimate", "Unknown")

    # Build existing data section
    existing_lines = []
    if company.get("cached_from_run_id"):
        freshness = company.get("data_freshness", "unknown")
        existing_lines.append(f"EXISTING DATA (from previous run, last updated: {freshness}):")
        existing_lines.append(f"  Employee count: {employee_count}")
        existing_lines.append(f"  Revenue estimate: ${revenue:,}" if isinstance(revenue, (int, float)) else f"  Revenue estimate: {revenue}")
        existing_lines.append(f"  Description: {description[:200]}")
        existing_lines.append("  Your job: VERIFY this data is still current AND find any NEW information.")
    existing_data = "\n".join(existing_lines) if existing_lines else ""

    # Determine which signals to research
    sections = []
    if signal_type in ("budget_signals", "both"):
        budget_cfg = icp.get("budget_signals", {})
        budget_signals = budget_cfg.get("signals", [])
        budget_condition = budget_cfg.get("condition", "OR")
        condition_text = f"Match condition: {budget_condition} — company must show {'ALL' if budget_condition == 'AND' else 'ANY'} of these signals."
        sections.append(f"""BUDGET SIGNALS TO RESEARCH:
{chr(10).join(f'  - {s}' for s in budget_signals) if budget_signals else '  - General budget capacity indicators (funding, revenue growth, tech investment)'}
{condition_text}

For EACH budget signal, actively research whether {name} shows evidence of it.
Also look for ADDITIONAL budget signals beyond what the user listed.""")

    if signal_type in ("urgency_signals", "both"):
        urgency_cfg = icp.get("urgency_signals", {})
        urgency_signals = urgency_cfg.get("signals", [])
        urgency_condition = urgency_cfg.get("condition", "OR")
        condition_text = f"Match condition: {urgency_condition} — company must show {'ALL' if urgency_condition == 'AND' else 'ANY'} of these signals."
        sections.append(f"""URGENCY SIGNALS TO RESEARCH:
{chr(10).join(f'  - {s}' for s in urgency_signals) if urgency_signals else '  - General buying urgency indicators (RFPs, new leadership, strategic shifts)'}
{condition_text}

For EACH urgency signal, actively research whether {name} shows evidence of it.
Also look for ADDITIONAL urgency signals beyond what the user listed.""")

    signal_sections = "\n\n".join(sections)

    return f"""Research {"budget and urgency" if signal_type == "both" else signal_type.replace("_", " ")} signals for this company.

COMPANY: {name}
DOMAIN: {domain}
EMPLOYEES: {employee_count}
REVENUE: {f'${revenue:,}' if isinstance(revenue, (int, float)) else revenue}
DESCRIPTION: {description[:300]}

{existing_data}

{signal_sections}

Use AT LEAST 3-4 different tools per company. Depth is critical — runtime doesn't matter.
If existing data is older than 90 days, refresh it with new searches.

OUTPUT FORMAT:
```json
{{
  "name": "{name}",
  "website": "{domain}",
  {"budget_signal_score" if signal_type != "urgency_signals" else "urgency_signal_score"}: 72,
  {'"urgency_signal_score": 65,' if signal_type == "both" else ""}
  "signals": [
    {{
      "type": "budget",
      "signal": "Signal name",
      "score": 4,
      "description": "Evidence description",
      "source_url": "https://...",
      "tool": "tavily_search",
      "confidence": "high"
    }}
  ],
  "composite_score": 72,
  "confidence_level": "high"
}}
```"""


# ──────────────────────────────────────────────────────────────────
# Stage 4: Contact Discovery (rewritten)
# ──────────────────────────────────────────────────────────────────

def build_contact_discovery_prompt(company: dict, icp: dict, cached_contacts: list | None = None) -> str:
    """Build prompt for Stage 4 — contact discovery for a single company."""
    ar = icp.get("authority_roles", {})
    target_roles = ar.get("target_roles", ["CEO", "CTO", "COO", "VP Engineering"])

    name = company.get("name", "Unknown")
    domain = company.get("website", "unknown")
    industry = company.get("industry", "")
    employee_count = company.get("employee_count", "")

    # Build cached contacts section
    cached_section = ""
    if cached_contacts:
        contact_lines = []
        for c in cached_contacts:
            contact_lines.append(
                f"  - {c.get('full_name', 'Unknown')}: {c.get('designation', 'Unknown role')} "
                f"(email: {c.get('email', 'N/A')}, linkedin: {c.get('linkedin_url', 'N/A')}, "
                f"source: {c.get('source', 'unknown')})"
            )
        cached_section = f"""
CACHED CONTACTS (from a previous pipeline run):
{chr(10).join(contact_lines)}

Review these cached contacts:
- Are these people likely still at this company? (>3 years in role may have moved)
- Mark each as "needs_verification" or "likely_current"."""

    # Industry hint for tool queries
    industry_hint = ""
    fd = icp.get("firmographic_details", {})
    for item in fd.get("industry_types", []):
        if isinstance(item, dict):
            industry_hint = item.get("vertical", "")
            break

    return f"""Find decision-maker contacts for this company.

COMPANY: {name}
DOMAIN: {domain}
INDUSTRY: {industry}
EMPLOYEES: {employee_count}

TARGET ROLES: {', '.join(target_roles)}
INDUSTRY HINT: "{industry_hint}"
{cached_section}

═══════════════════════════════════════════
STEP 1: USE YOUR TRAINING KNOWLEDGE
═══════════════════════════════════════════
Before calling ANY tools, think about what you already know about {name}:
- Do you know the CEO, CTO, or other executives from your training data?
- Is this a well-known company whose leadership you can name?
List any contacts you can identify from memory. These will be VERIFIED in the next steps.

═══════════════════════════════════════════
STEP 2: TOOL-BASED DISCOVERY & VERIFICATION
═══════════════════════════════════════════
Use ALL of these methods. Do NOT skip any:

A. PAID DATABASE (highest quality):
   → apollo_people_search: Search with target roles [{', '.join(target_roles)}]. Paginate (page 1,2,3).

B. MULTI-METHOD EXECUTIVE FINDER:
   → find_company_executives: Uses 7 independent methods. Always call this.
   → research_company: Gets contacts + financial/news data in one call.

C. LINKEDIN INTELLIGENCE:
   → find_linkedin_profiles: Batch LinkedIn search for target roles.
   → For contacts from Step 1 (training knowledge), use duckduckgo_search:
     "[Name] {name} LinkedIn" to verify they're still at the company.

D. WEBSITE SCRAPING:
   → scrape_team_page: Scan /team, /about, /leadership pages.
   → scrape_webpage: Read specific pages (e.g., press releases naming executives).

E. EMAIL & PHONE ENRICHMENT:
   → hunter_domain_search: Find email patterns for {domain}.
   → hunter_email_finder: Verify specific person's email.
   → lusha_person_search: Get phone numbers (requires LinkedIn URL or email).

F. JOB POSTING INTELLIGENCE:
   → search_job_postings: Check open positions for org structure signals.

G. NEWS & PRESS:
   → tavily_search: "{name} CEO interview" or "{name} executive appointment"
   → exa_search: Search for conference speakers, thought leaders at this company.

═══════════════════════════════════════════
STEP 3: CROSS-REFERENCE & CONFIDENCE SCORING
═══════════════════════════════════════════
- Contacts found by 3+ sources → confidence 0.95
- Contacts found by 2 sources → confidence 0.80
- Contacts found by 1 source → confidence 0.60
- Contacts from training knowledge only (not verified) → confidence 0.40
- Inferred emails → confidence 0.30

Deduplicate by LinkedIn URL, then by (full_name + company). Merge data across sources.

OUTPUT FORMAT:
```json
{{
  "name": "{name}",
  "website": "{domain}",
  "contacts": [
    {{
      "full_name": "Jane Doe",
      "first_name": "Jane",
      "last_name": "Doe",
      "designation": "Chief Technology Officer",
      "role_category": "CTO",
      "email": "jane@{domain}",
      "phone": null,
      "linkedin_url": "https://linkedin.com/in/janedoe",
      "source": "apollo_people_search",
      "confidence": 0.80,
      "enrichment_status": "enriched"
    }}
  ],
  "research_data": {{
    "financials": "Summary of financial data found",
    "news": "Summary of recent news",
    "tech_signals": ["signal1", "signal2"],
    "source_urls": [
      {{"url": "https://...", "title": "Page title", "tool": "research_company"}}
    ]
  }}
}}
```"""
