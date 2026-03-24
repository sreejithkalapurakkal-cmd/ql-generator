"""Prompt builders for the 5-stage pipeline.

Each builder constructs the user-facing prompt for one agent invocation,
injecting ICP criteria, cached data, and stage-specific context.
"""
import json
from datetime import datetime, timezone

from app.tools.query_strategy import get_industry_queries, get_strategy_summary, expand_industry_keywords


# ──────────────────────────────────────────────────────────────────
# Geographic hub mapping for industry-aware discovery
# ──────────────────────────────────────────────────────────────────

GEOGRAPHY_HUBS: dict[str, list[str]] = {
    "united states": ["San Francisco", "New York", "Boston", "Austin", "Seattle", "Chicago", "Los Angeles", "San Diego", "Denver", "Miami"],
    "usa": ["San Francisco", "New York", "Boston", "Austin", "Seattle", "Chicago", "Los Angeles", "San Diego", "Denver", "Miami"],
    "united kingdom": ["London", "Cambridge", "Oxford", "Manchester", "Edinburgh", "Bristol"],
    "uk": ["London", "Cambridge", "Oxford", "Manchester", "Edinburgh", "Bristol"],
    "germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Stuttgart"],
    "france": ["Paris", "Lyon", "Toulouse", "Sophia Antipolis"],
    "india": ["Bangalore", "Mumbai", "Hyderabad", "Pune", "Delhi NCR", "Chennai"],
    "israel": ["Tel Aviv", "Herzliya", "Haifa", "Jerusalem"],
    "canada": ["Toronto", "Vancouver", "Montreal", "Waterloo", "Calgary"],
    "australia": ["Sydney", "Melbourne", "Brisbane", "Perth"],
    "singapore": ["Singapore"],
    "japan": ["Tokyo", "Osaka", "Nagoya"],
    "china": ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Guangzhou"],
    "netherlands": ["Amsterdam", "Eindhoven", "Rotterdam"],
    "sweden": ["Stockholm", "Gothenburg", "Malmö"],
    "switzerland": ["Zurich", "Basel", "Geneva", "Lausanne"],
}


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

def build_industry_discovery_prompt(icp: dict, kb_known_domains: list[str] | None = None) -> str:
    """Build prompt for Stage 1 — discover ALL companies matching industry + geography."""
    kw = _extract_keywords(icp)
    fd = icp.get("firmographic_details", {})

    industry_text = ", ".join(kw["industry_keywords"])
    sub_vert_text = ", ".join(kw["sub_verticals"]) if kw["sub_verticals"] else "N/A"
    regions_text = ", ".join(kw["regions"]) if kw["regions"] else "Global"

    # Expand keywords with industry synonyms for broader query coverage
    all_keywords = kw["industry_keywords"] + kw["sub_verticals"]
    expanded_keywords = expand_industry_keywords(all_keywords)
    synonyms_added = [s for s in expanded_keywords if s not in all_keywords]

    # Get industry-specific query suggestions (using expanded keywords)
    suggested_queries = get_industry_queries(expanded_keywords, kw["regions"], max_queries=10)
    strategy_info = get_strategy_summary(all_keywords)

    query_suggestions_text = ""
    if suggested_queries:
        query_lines = "\n".join(f"  - {q}" for q in suggested_queries)
        query_suggestions_text = f"""
INDUSTRY-SPECIFIC SEARCH QUERIES (use these with duckduckgo_search, tavily_search, or exa_search):
{query_lines}
"""

    # Build Apollo-specific parameter guidance
    apollo_params = []
    if kw["rev_min"] or kw["rev_max"]:
        # Map ICP revenue to Apollo's revenue range buckets
        apollo_rev_ranges = []
        rev_buckets = [
            (0, 1_000_000, "0,1000000"),
            (1_000_000, 10_000_000, "1000000,10000000"),
            (10_000_000, 50_000_000, "10000000,50000000"),
            (50_000_000, 100_000_000, "50000000,100000000"),
            (100_000_000, 500_000_000, "100000000,500000000"),
            (500_000_000, 1_000_000_000, "500000000,1000000000"),
            (1_000_000_000, float('inf'), "1000000000,"),
        ]
        rmin = (kw["rev_min"] or 0) * 0.3  # generous lower margin
        rmax = (kw["rev_max"] or float('inf')) * 3  # generous upper margin
        for bmin, bmax, bstr in rev_buckets:
            if bmax > rmin and bmin < rmax:
                apollo_rev_ranges.append(bstr)
        if apollo_rev_ranges:
            apollo_params.append(f'    revenue_range={json.dumps(apollo_rev_ranges)}')

    if kw["emp_min"] or kw["emp_max"]:
        apollo_params.append(f'    min_employees={int((kw["emp_min"] or 1) * 0.5)}, max_employees={int((kw["emp_max"] or 100000) * 2)}')

    if kw["regions"]:
        apollo_params.append(f'    locations={json.dumps(kw["regions"])}')

    apollo_guidance = ""
    if apollo_params:
        apollo_guidance = f"""
  MANDATORY APOLLO PARAMETERS — use EXACTLY these filters in EVERY apollo_company_search
  and apollo_company_search_paginated call:
{chr(10).join(apollo_params)}
  CRITICAL: Calls WITHOUT these filters return irrelevant companies and waste your tool budget.
  These use generous margins — Stage 2 will verify exact fit."""

    # Build Exa-specific size/location guidance
    exa_guidance = ""
    if kw["emp_min"] and kw["emp_max"]:
        if kw["emp_max"] <= 200:
            size_desc = "small"
        elif kw["emp_max"] <= 1000:
            size_desc = "mid-size"
        else:
            size_desc = "large"
        exa_examples = []
        for sv in (kw["sub_verticals"] or kw["industry_keywords"])[:2]:
            for r in (kw["regions"] or [""])[:2]:
                q = f'"{size_desc} {sv} companies'
                if r:
                    q += f" in {r}"
                q += '"'
                exa_examples.append(q)
        exa_guidance = f"""
  EXA QUERY TIPS (exa_search responds well to natural language):
  Include company size in queries to get better-matched results:
    {chr(10).join(f"  - {ex}" for ex in exa_examples)}
  Always use category="company" for discovery queries.
"""

    # Build per-subvertical per-region query matrix
    query_matrix = []
    svs = kw["sub_verticals"] if kw["sub_verticals"] else kw["industry_keywords"]
    regs = kw["regions"] if kw["regions"] else [""]
    for sv in svs[:4]:
        for r in regs[:3]:
            query_matrix.append(f'"{sv} companies{" in " + r if r else ""}"')
    if kw["emp_min"] and kw["emp_max"]:
        for sv in svs[:2]:
            query_matrix.append(f'"{sv} companies {kw["emp_min"]}-{kw["emp_max"]} employees"')
    for kw_item in kw["industry_keywords"][:2]:
        query_matrix.append(f'"fastest growing {kw_item} companies 2025 2026"')
        query_matrix.append(f'"top {kw_item} startups funded"')

    query_matrix_text = ""
    if query_matrix:
        lines = "\n".join(f"  - {q}" for q in query_matrix[:15])
        query_matrix_text = f"""
CROSS-PRODUCT QUERY MATRIX (use with exa_search, tavily_search, apollo_company_search):
{lines}
"""

    # Build synonym section
    synonym_section = ""
    if synonyms_added:
        synonym_section = f"""
INDUSTRY SYNONYMS (use as query variations for broader coverage):
  {', '.join(synonyms_added)}
"""

    # Build geographic hubs section
    geo_hubs_section = ""
    if kw["regions"]:
        hub_lines = []
        for region in kw["regions"][:5]:
            region_lower = region.lower().strip()
            hubs = GEOGRAPHY_HUBS.get(region_lower, [])
            if hubs:
                hub_lines.append(f"  {region}: {', '.join(hubs[:6])}")
        if hub_lines:
            geo_hubs_section = f"""
KEY INDUSTRY HUBS (search for companies in these cities):
{chr(10).join(hub_lines)}
"""

    # Build KB known-domains section
    kb_domains_section = ""
    if kb_known_domains:
        display_domains = kb_known_domains[:300]
        domain_lines = ", ".join(display_domains)
        kb_domains_section = f"""
COMPANIES ALREADY IN KNOWLEDGE BASE ({len(kb_known_domains)} known):
These companies have been found and scored in previous pipeline runs. They will be auto-enriched
from the knowledge base. You should still INCLUDE them in your output if they match the ICP, but
PRIORITIZE finding NEW companies not in this list. Do NOT spend tool calls researching these:
{domain_lines}
{"... and " + str(len(kb_known_domains) - 300) + " more" if len(kb_known_domains) > 300 else ""}
"""

    return f"""Discover ALL companies matching the following industry, vertical, and geography criteria.
There is NO upper limit on company count — find as many as possible. Aim for atleast 500 companies
without breaking the search criteria.

INDUSTRY: {industry_text}
SUB-VERTICALS: {sub_vert_text}
GEOGRAPHY: {regions_text}
{synonym_section}{geo_hubs_section}{kb_domains_section}
STEP 1 — KNOWLEDGE BASE:
Call search_kb_companies with industry and country filters AND icp_description="{industry_text} companies in {regions_text}".
The icp_description ranks results by semantic similarity to the current ICP. Returns all matches (deduplicated, one per domain).

STEP 2 — STRUCTURED TRAINING KNOWLEDGE RECALL:
Think systematically through these categories for {industry_text} / {sub_vert_text} in {regions_text}:

TIER 1 - MARKET LEADERS: Public companies, unicorns, household names in this industry.
TIER 2 - MID-MARKET: Companies known from industry awards, "top X" lists, trade press coverage.
TIER 3 - INDUSTRY NETWORK: Conference sponsors/exhibitors, association members, VC portfolio companies.
TIER 4 - GEOGRAPHIC CLUSTERS: Companies in known hubs for this industry in {regions_text}.
TIER 5 - ADJACENT & EMERGING: Recent startups, companies in overlapping sub-verticals, acqui-hires.

Aim for 50-100 companies across all tiers. Be exhaustive — list every company you know.

STEP 3 — STRUCTURED DATABASE DISCOVERY (FREE, HIGH VOLUME):
Call these tools FIRST — they return many companies with clean structured data:
- search_wikidata_companies: Pass industry_keywords={json.dumps(all_keywords[:3])} and
  countries={json.dumps(kw['regions'][:3])}. FREE, no rate limits. Returns name, website,
  employee count, revenue, headquarters for established companies.
- search_french_companies: FREE, no auth. 12M French companies with employee counts, directors,
  industry codes. Use when ICP targets France. Query: "{all_keywords[0] if all_keywords else 'company'}".
- search_nordic_companies: FREE, no auth. Danish, Norwegian, Swedish companies with employee
  counts and industry codes. Use country="dk"/"no"/"se" matching ICP geography.
- search_uk_companies: FREE (API key). 5M UK companies with SIC codes and officers.
  Use when ICP targets United Kingdom.

STEP 4 — API-BASED DISCOVERY:
- apollo_company_search_paginated: AUTO-PAGINATES through multiple pages. Use max_pages=5 for broad
  queries, max_pages=10 for high-value primary queries. Returns 75-250 results per call.
  Use sub-vertical + region combinations. Make 3-5 calls with different keyword combinations.
- apollo_company_search: Use for single-page targeted lookups (per_page=100).
{apollo_guidance}
- exa_search: Run 8-12 different query angles. Use category="company" to filter for company sites.
  Vary keywords, regions, adjacent terms. num_results defaults to 30 per call.
{exa_guidance}
- exa_find_similar: After finding 3-5 high-quality company matches, use their website URLs to
  discover similar companies. This is very effective for finding companies you wouldn't find by keyword.
  Example: exa_find_similar(url="https://good-match.com", num_results=30, category="company")
- discover_icp_companies: Use for broad DDG-based batch discovery. 2-3 calls.
- search_yc_companies: Check YC directory for startups in this vertical.
- tavily_search: Search for "top {industry_text} companies" lists, directories, rankings.
  max_results defaults to 15 per call. Use include_domains for business directories.
- duckduckgo_search: Search for industry directories, associations, conference exhibitor lists.
- scrape_webpage: Scrape industry directories and "top companies" lists found by other tools.
{query_suggestions_text}{query_matrix_text}
TOOL BUDGET: You have ~40 tool calls. Plan your strategy:
  1st priority: Apollo (structured, high volume) — 10+ calls
  2nd priority: Exa search + findSimilar (semantic) — 8+ calls
  3rd priority: Structured DBs (Wikidata) + GitHub/Patents — 2-3 calls
  4th priority: Tavily, DDG, YC, scraping — remaining calls

MINIMUM REQUIREMENTS: You MUST call at least 4 different tools. If Apollo returns <50 results
for a query, try different keyword combinations or use exa_find_similar to expand.

Use the MANDATORY APOLLO PARAMETERS above to guide discovery toward the right company size and geography.

CRITICAL — VOLUME OVER PRECISION:
Do NOT manually exclude or cherry-pick companies. When a tool returns 200 results, include ALL 200
in your JSON output — even if some seem borderline. The pipeline handles deduplication and filtering
in Stage 2. Your job is to maximize raw count. Every company returned by a tool that matches the
industry AND geography belongs in your output.

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
    "tools_used": {{"apollo_company_search": 12, "exa_search": 10, "search_wikidata_companies": 1}}
  }}
}}
```"""


def build_discovery_web_prompt(icp: dict, already_found_count: int, known_domains: list[str] = None) -> str:
    """Build prompt for Stage 1 web-search sub-run.

    This is used when doing chunked discovery: the structured-data sub-run
    has already found `already_found_count` companies, and now the web-search
    sub-run looks for additional companies not in databases.
    """
    kw = _extract_keywords(icp)
    all_keywords = kw["industry_keywords"] + kw["sub_verticals"]
    industry_text = ", ".join(kw["industry_keywords"])
    sub_vert_text = ", ".join(kw["sub_verticals"]) if kw["sub_verticals"] else "N/A"
    regions_text = ", ".join(kw["regions"]) if kw["regions"] else "Global"

    # Get industry-specific queries for web search
    suggested_queries = get_industry_queries(all_keywords, kw["regions"], max_queries=10)
    query_lines = "\n".join(f"  - {q}" for q in suggested_queries) if suggested_queries else ""

    # Build known domains section to avoid duplicates
    known_domains_section = ""
    if known_domains:
        # Limit to 200 domains to avoid prompt bloat
        display_domains = known_domains[:200]
        domain_lines = ", ".join(display_domains)
        known_domains_section = f"""
ALREADY FOUND BY OTHER TOOLS IN THIS RUN ({len(known_domains)} domains):
These were found by structured database searches. FOCUS on finding NEW companies not in this list.
If you independently find one of these in a larger result set, that is fine — just do not spend
extra tool calls specifically re-researching companies already on this list.
{domain_lines}
{"... and " + str(len(known_domains) - 200) + " more" if len(known_domains) > 200 else ""}
"""

    return f"""Find ADDITIONAL companies in {industry_text} / {sub_vert_text} in {regions_text}
that were NOT found by structured databases. {already_found_count} companies already discovered.

Use web search tools to find companies from:
- Industry directories and association member lists
- Conference exhibitor lists and award rankings
- News articles mentioning companies in this space
- Startup databases and accelerator portfolios
{known_domains_section}
RECOMMENDED SEARCH QUERIES:
{query_lines}

Return JSON with "companies" array. Same format as before:
name, website, industry, sub_industry, country, city, employee_count,
revenue_estimate, description, source.

All scores must be on 0-100 integer scale (NOT 0-10)."""


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

For EACH company output (score MUST be on 0-100 integer scale, NOT 0-10):
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

RECENCY PRIORITY: Always include evidence_date (YYYY-MM-DD) and recency_months for each signal.
Recent evidence (<3 months) is weighted much more heavily than old evidence (>6 months).

OUTPUT FORMAT (all scores MUST be on 0-100 integer scale, NOT 0-10):
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
      "confidence": "high",
      "evidence_date": "2026-02-15",
      "recency_months": 1.1
    }}
  ],
  "composite_score": 72,
  "confidence_level": "high"
}}
```"""


# ──────────────────────────────────────────────────────────────────
# Stage 3 batch: Grouped signal research (C3)
# ──────────────────────────────────────────────────────────────────

def build_batch_signal_prompt(companies: list[dict], icp: dict, signal_type: str) -> str:
    """Build prompt for Stage 3 batch signal research — multiple companies at once.

    Groups companies from the same industry so shared industry signals
    (e.g., regulatory changes, market trends) are researched once.

    Args:
        companies: List of company dicts
        icp: Full ICP config
        signal_type: "budget_signals", "urgency_signals", or "both"
    """
    # Build signal requirements section (same for all companies)
    sections = []
    if signal_type in ("budget_signals", "both"):
        budget_cfg = icp.get("budget_signals", {})
        budget_signals = budget_cfg.get("signals", [])
        budget_condition = budget_cfg.get("condition", "OR")
        condition_text = f"Match condition: {budget_condition} — company must show {'ALL' if budget_condition == 'AND' else 'ANY'} of these signals."
        sections.append(f"""BUDGET SIGNALS TO RESEARCH:
{chr(10).join(f'  - {s}' for s in budget_signals) if budget_signals else '  - General budget capacity indicators (funding, revenue growth, tech investment)'}
{condition_text}""")

    if signal_type in ("urgency_signals", "both"):
        urgency_cfg = icp.get("urgency_signals", {})
        urgency_signals = urgency_cfg.get("signals", [])
        urgency_condition = urgency_cfg.get("condition", "OR")
        condition_text = f"Match condition: {urgency_condition} — company must show {'ALL' if urgency_condition == 'AND' else 'ANY'} of these signals."
        sections.append(f"""URGENCY SIGNALS TO RESEARCH:
{chr(10).join(f'  - {s}' for s in urgency_signals) if urgency_signals else '  - General buying urgency indicators (RFPs, new leadership, strategic shifts)'}
{condition_text}""")

    signal_sections = "\n\n".join(sections)

    # Build company list
    company_entries = []
    for i, c in enumerate(companies, 1):
        name = c.get("name", "Unknown")
        domain = c.get("website", "unknown")
        desc = c.get("description", "")[:200]
        emp = c.get("employee_count", "Unknown")
        rev = c.get("revenue_estimate", "Unknown")
        rev_str = f"${rev:,}" if isinstance(rev, (int, float)) else str(rev)

        company_entries.append(
            f"  Company {i}: {name} | {domain} | Employees: {emp} | Revenue: {rev_str}\n"
            f"    Description: {desc}"
        )

    companies_block = "\n".join(company_entries)

    # Identify shared industry (if any)
    industries = set()
    for c in companies:
        ind = c.get("industry", "")
        if ind:
            industries.add(ind)
    industry_note = ""
    if industries:
        industry_note = f"""
SHARED INDUSTRY CONTEXT: {', '.join(industries)}
First research SHARED industry-level signals (regulatory changes, market trends,
industry funding rounds, major industry events) that apply to ALL companies.
Then research company-SPECIFIC signals for each company individually.
This saves time and provides richer context."""

    signal_label = "budget and urgency" if signal_type == "both" else signal_type.replace("_", " ")
    score_line = '"budget_signal_score": 72,' if signal_type != "urgency_signals" else '"urgency_signal_score": 72,'
    urgency_line = '"urgency_signal_score": 65,' if signal_type == "both" else ""

    return f"""Research {signal_label} signals for {len(companies)} companies in a BATCH.

COMPANIES:
{companies_block}
{industry_note}

{signal_sections}

INSTRUCTIONS:
1. Research SHARED industry signals first (1-2 tool calls covering all companies)
2. Then research per-company signals (2-3 tool calls per company)
3. Use at least 2 different tools per company

RECENCY PRIORITY: Always include evidence_date (YYYY-MM-DD) and recency_months for each signal.
Recent evidence (<3 months) is weighted much more heavily than old evidence (>6 months).
A funding round from 18 months ago weighs far less than a hiring spree from last week.

OUTPUT FORMAT (all scores MUST be on 0-100 integer scale, NOT 0-10):
```json
{{
  "companies": [
    {{
      "name": "Company Name",
      "website": "domain.com",
      {score_line}
      {urgency_line}
      "signals": [
        {{
          "type": "budget",
          "signal": "Signal name",
          "score": 4,
          "description": "Evidence description",
          "source_url": "https://...",
          "tool": "tavily_search",
          "confidence": "high",
          "evidence_date": "2026-02-15",
          "recency_months": 1.1
        }}
      ],
      "composite_score": 72,
      "confidence_level": "high"
    }}
  ],
  "shared_industry_signals": [
    {{
      "signal": "Industry trend description",
      "type": "budget",
      "applies_to": ["Company A", "Company B"],
      "source_url": "https://..."
    }}
  ]
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

E. JOB POSTING INTELLIGENCE:
   → search_job_postings: Check open positions for org structure signals.

F. NEWS & PRESS:
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
