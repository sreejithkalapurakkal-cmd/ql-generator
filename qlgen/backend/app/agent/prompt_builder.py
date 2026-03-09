import json


def _format_icp_sections(icp: dict) -> str:
    """Format ICP config into readable sections for agent prompts.

    Covers all 9 ICP dimensions: target offering, geography (with priority areas),
    industry (with sub-verticals), company size, technology maturity (with negative
    signals), infrastructure readiness, digital transformation drivers (4 sub-fields),
    and leadership traits (with behavioral traits).
    """
    sections = []

    # 1. Target Offering
    offering = icp.get("target_offering") or icp.get("offering")
    if offering:
        sections.append(f"TARGET OFFERING: {json.dumps(offering)}")

    # 2. Geography + Priority Areas
    regions = icp.get("regions")
    if regions:
        countries = regions.get("countries", [])
        priority_areas = regions.get("priority_areas", [])
        geo_lines = ["GEOGRAPHY:"]
        if countries:
            geo_lines.append(f"  Countries: {', '.join(countries)}")
        if priority_areas:
            geo_lines.append(f"  Priority Areas: {', '.join(priority_areas)}")
        sections.append("\n".join(geo_lines))

    # 3. Industry Types + Sub-verticals
    industry = icp.get("industry_types") or icp.get("industry")
    if industry:
        if isinstance(industry, list):
            ind_lines = ["INDUSTRY TYPES:"]
            for item in industry:
                if isinstance(item, dict):
                    vertical = item.get("vertical", "")
                    sub_vertical = item.get("sub_vertical", "")
                    if sub_vertical:
                        ind_lines.append(f"  - {vertical} > {sub_vertical}")
                    elif vertical:
                        ind_lines.append(f"  - {vertical}")
                else:
                    ind_lines.append(f"  - {item}")
            sections.append("\n".join(ind_lines))
        else:
            sections.append(f"INDUSTRY TYPES: {json.dumps(industry)}")

    # 4. Company Size
    cs = icp.get("company_size") or icp.get("size")
    if cs:
        emp = cs.get("employee_range") or {}
        emp_min = emp.get("min") if emp else cs.get("employees_min", "N/A")
        emp_max = emp.get("max") if emp else cs.get("employees_max", "N/A")
        rev = cs.get("revenue_range") or {}
        rev_min = rev.get("min") if rev else cs.get("revenue_min", "N/A")
        rev_max = rev.get("max") if rev else cs.get("revenue_max", "N/A")
        currency = cs.get("revenue_currency", "USD")
        sections.append(f"COMPANY SIZE: {emp_min}-{emp_max} employees, ${rev_min}-${rev_max} {currency}")

    # 5. Technology Maturity (positive + negative signals)
    tm = icp.get("technology_maturity") or icp.get("tech")
    if tm:
        positive = tm.get("positive_signals", tm.get("signals", []))
        negative = tm.get("negative_signals", [])
        tech_lines = ["TECHNOLOGY MATURITY:"]
        if positive:
            tech_lines.append(f"  Positive: {', '.join(positive)}")
        if negative:
            tech_lines.append(f"  Negative (DISQUALIFIERS): {', '.join(negative)}")
        sections.append("\n".join(tech_lines))

    # 6. Infrastructure Readiness
    ir = icp.get("infrastructure_readiness")
    if ir:
        indicators = ir.get("indicators", [])
        if indicators:
            sections.append(f"INFRASTRUCTURE READINESS: {', '.join(indicators)}")

    # 7. Digital Transformation Drivers (all 4 sub-fields)
    dtd = icp.get("digital_transformation_drivers") or icp.get("drivers")
    if dtd:
        dt_lines = ["DIGITAL TRANSFORMATION DRIVERS:"]
        triggers = dtd.get("growth_triggers", [])
        pains = dtd.get("operational_pains", [])
        pressures = dtd.get("competitive_pressures", [])
        initiatives = dtd.get("strategic_initiatives", [])
        if triggers:
            dt_lines.append(f"  Growth Triggers: {', '.join(triggers)}")
        if pains:
            dt_lines.append(f"  Operational Pains: {', '.join(pains)}")
        if pressures:
            dt_lines.append(f"  Competitive Pressures: {', '.join(pressures)}")
        if initiatives:
            dt_lines.append(f"  Strategic Initiatives: {', '.join(initiatives)}")
        sections.append("\n".join(dt_lines))

    # 8. Leadership Traits (roles + behavioral)
    lt = icp.get("leadership_traits") or icp.get("leadership")
    if lt:
        roles = lt.get("target_roles", [])
        traits = lt.get("behavioral_traits", [])
        lead_lines = ["LEADERSHIP TRAITS:"]
        if roles:
            lead_lines.append(f"  Target Roles: {', '.join(roles)}")
        if traits:
            lead_lines.append(f"  Behavioral Traits: {', '.join(traits)}")
        sections.append("\n".join(lead_lines))

    return "\n".join(sections)


def _extract_icp_keywords(icp: dict) -> dict:
    """Extract structured keywords from all ICP dimensions for multi-tool discovery.

    Returns a dict with keys:
        industry_keywords, sub_verticals, regions, priority_areas,
        emp_min, emp_max, rev_min, rev_max, size_hint,
        offering_terms, tech_signals, negative_signals,
        infra_indicators, transformation_keywords,
        target_roles, behavioral_traits
    """
    # Industry keywords (verticals + sub-verticals)
    industry_keywords = []
    sub_verticals = []
    industry = icp.get("industry_types") or icp.get("industry")
    if industry:
        if isinstance(industry, list):
            for item in industry:
                if isinstance(item, dict):
                    v = item.get("vertical", "")
                    sv = item.get("sub_vertical", "")
                    if v:
                        industry_keywords.append(v)
                    if sv:
                        sub_verticals.append(sv)
                else:
                    industry_keywords.append(str(item))
        elif isinstance(industry, str):
            industry_keywords.append(industry)

    # Regions + priority areas
    regions = []
    priority_areas = []
    r = icp.get("regions")
    if r:
        regions = r.get("countries", [])
        priority_areas = r.get("priority_areas", [])

    # Size ranges
    emp_min = emp_max = rev_min = rev_max = None
    size_hint = ""
    cs = icp.get("company_size") or icp.get("size")
    if cs:
        emp = cs.get("employee_range") or {}
        emp_min = emp.get("min") if emp else cs.get("employees_min")
        emp_max = emp.get("max") if emp else cs.get("employees_max")
        rev = cs.get("revenue_range") or {}
        rev_min = rev.get("min") if rev else cs.get("revenue_min")
        rev_max = rev.get("max") if rev else cs.get("revenue_max")
        if emp_min and emp_max:
            size_hint = f"mid-size {emp_min}-{emp_max} employees"

    # Offering terms
    offering_terms = []
    offering = icp.get("target_offering") or icp.get("offering")
    if offering and isinstance(offering, list):
        for o in offering[:5]:
            if isinstance(o, str):
                short = o.split("-")[0].split(",")[0].strip()[:60]
                offering_terms.append(short)

    # Technology maturity (positive + negative)
    tech_signals = []
    negative_signals = []
    tm = icp.get("technology_maturity") or icp.get("tech")
    if tm:
        tech_signals = tm.get("positive_signals", tm.get("signals", []))
        negative_signals = tm.get("negative_signals", [])

    # Infrastructure readiness
    infra_indicators = []
    ir = icp.get("infrastructure_readiness")
    if ir:
        infra_indicators = ir.get("indicators", [])

    # Digital transformation drivers (merged from all 4 sub-fields)
    transformation_keywords = []
    dtd = icp.get("digital_transformation_drivers") or icp.get("drivers")
    if dtd:
        for field in ("growth_triggers", "operational_pains", "competitive_pressures", "strategic_initiatives"):
            transformation_keywords.extend(dtd.get(field, []))

    # Leadership traits
    target_roles = []
    behavioral_traits = []
    lt = icp.get("leadership_traits") or icp.get("leadership")
    if lt:
        target_roles = lt.get("target_roles", [])
        behavioral_traits = lt.get("behavioral_traits", [])

    return {
        "industry_keywords": industry_keywords,
        "sub_verticals": sub_verticals,
        "regions": regions,
        "priority_areas": priority_areas,
        "emp_min": emp_min,
        "emp_max": emp_max,
        "rev_min": rev_min,
        "rev_max": rev_max,
        "size_hint": size_hint,
        "offering_terms": offering_terms,
        "tech_signals": tech_signals,
        "negative_signals": negative_signals,
        "infra_indicators": infra_indicators,
        "transformation_keywords": transformation_keywords,
        "target_roles": target_roles,
        "behavioral_traits": behavioral_traits,
    }


def _group_regions_into_zones(regions: list[str]) -> list[dict]:
    """Group countries into geographic zones for balanced multi-region search.

    Returns a list of zone dicts with 'name' and 'countries' keys,
    ensuring each zone has at most 4 countries for focused API calls.
    """
    # Known region mappings — extend as needed
    REGION_MAP = {
        # North America
        "USA": "americas", "US": "americas", "United States": "americas",
        "CANADA": "americas", "Canada": "americas",
        "Mexico": "americas", "Brazil": "americas", "Colombia": "americas",
        "Argentina": "americas", "Chile": "americas",
        # Europe
        "Germany": "europe", "UK": "europe", "United Kingdom": "europe",
        "France": "europe", "Netherlands": "europe", "Switzerland": "europe",
        "Belgium": "europe", "Sweden": "europe", "Norway": "europe",
        "Denmark": "europe", "Finland": "europe", "Ireland": "europe",
        "Austria": "europe", "Spain": "europe", "Italy": "europe",
        "Poland": "europe", "Czech Republic": "europe", "Portugal": "europe",
        # Asia-Pacific
        "Malaysia": "apac", "Thailand": "apac", "Vietnam": "apac",
        "Indonesia": "apac", "Singapore": "apac", "Philippines": "apac",
        "Japan": "apac", "South Korea": "apac", "Taiwan": "apac",
        "India": "apac", "Australia": "apac", "New Zealand": "apac",
        "China": "apac", "Hong Kong": "apac",
        # Middle East & Africa
        "UAE": "mea", "Saudi Arabia": "mea", "Israel": "mea",
        "South Africa": "mea", "Qatar": "mea", "Kenya": "mea",
    }

    ZONE_LABELS = {
        "americas": "Americas",
        "europe": "Europe",
        "apac": "Asia-Pacific",
        "mea": "Middle East & Africa",
    }

    zone_countries: dict[str, list[str]] = {}
    for country in regions:
        zone = REGION_MAP.get(country, "other")
        zone_countries.setdefault(zone, []).append(country)

    zones = []
    for zone_key, countries in zone_countries.items():
        label = ZONE_LABELS.get(zone_key, zone_key.title())
        zones.append({"name": label, "countries": countries})

    return zones


def _build_strictness_override(strictness: str) -> str:
    """Return prompt text overriding classification thresholds for strict/relaxed modes.

    Returns empty string for moderate (default), preserving current behavior exactly.
    """
    if strictness == "strict":
        return """

═══════════════════════════════════════════
OVERRIDE: STRICT MATCHING MODE
═══════════════════════════════════════════
You are operating in STRICT mode. Apply these REPLACEMENT thresholds (ignore the defaults above):

CLASSIFICATION (STRICT):
- verified_match: icp_match_score >= 80, ALL 4 critical dimensions (offering, geography, industry, size) score 2, AND 7+ dimensions have evidence
- potential_match: icp_match_score >= 65, ALL 4 critical dimensions score >= 1, AND 5+ dimensions have evidence
- weak_match: ELIMINATED — do NOT return any weak_match companies. Discard them entirely.
- DISCARD: icp_match_score < 65 OR any critical dimension scores 0

BEHAVIORAL RULES (STRICT):
- Prefer FEWER, higher-quality results over volume. Quality over quantity.
- Spend more time on verification — use scrape_webpage on company websites to confirm dimension evidence before classifying.
- If in doubt about a classification, demote the company to the lower tier or discard.
- Do NOT pad results with marginal matches."""
    elif strictness == "relaxed":
        return """

═══════════════════════════════════════════
OVERRIDE: RELAXED MATCHING MODE
═══════════════════════════════════════════
You are operating in RELAXED mode. Apply these REPLACEMENT thresholds (ignore the defaults above):

CLASSIFICATION (RELAXED):
- verified_match: icp_match_score >= 50, ALL 4 critical dimensions (offering, geography, industry, size) score >= 1, AND 5+ dimensions have evidence
- potential_match: icp_match_score >= 35, offering_fit >= 1, AND at least 1 other critical dimension (geography, industry, or size) scores >= 1
- weak_match: icp_match_score >= 20, offering_fit >= 1
- DISCARD: icp_match_score < 20 OR offering_fit = 0

BEHAVIORAL RULES (RELAXED):
- Cast a WIDER net. Include partial-match candidates that show promise on key dimensions.
- Prioritize breadth of discovery — find more companies rather than being overly selective.
- For EVERY company in your results, match_reasoning MUST explicitly list:
  (a) Which ICP criteria were met (with evidence)
  (b) Which ICP criteria were NOT met
  (c) Percentage of dimensions with positive evidence, e.g. "6 of 9 dimensions matched (67%)"
- This transparency is critical for relaxed mode — users need to see exactly what matched and what didn't."""
    return ""


def build_discovery_prompt(icp: dict, options: dict) -> str:
    """Build prompt for Phase 1 — multi-source company discovery with 9-dimension ICP scoring."""
    max_companies = options.get("max_companies", 25)
    icp_text = _format_icp_sections(icp)
    kw = _extract_icp_keywords(icp)

    # Group regions into geographic zones for balanced coverage
    zones = _group_regions_into_zones(kw["regions"])
    num_zones = len(zones)

    # Calculate per-zone targets (ensure every zone gets attention)
    per_zone_target = max(3, max_companies // max(num_zones, 1))

    # Build zone-specific Apollo call instructions
    apollo_calls = []
    for i, zone in enumerate(zones):
        apollo_calls.append(
            f"  Call {i+1} ({zone['name']}): query=primary industry, "
            f"locations={json.dumps(zone['countries'])}, "
            f"min_employees={kw['emp_min']}, max_employees={kw['emp_max']}"
        )
    # Add one extra call for sub-verticals across all regions
    apollo_calls.append(
        f"  Call {len(zones)+1} (sub-verticals): query=sub-vertical keywords, "
        f"locations={json.dumps(kw['regions'][:6])}"
    )

    # Build zone-specific Exa queries
    exa_queries = []
    industry_short = ' '.join(kw['industry_keywords'][:2])
    offering_short = ' '.join(kw['offering_terms'][:2]) if kw['offering_terms'] else ''
    for zone in zones:
        region_str = ', '.join(zone['countries'][:3])
        if offering_short:
            exa_queries.append(
                f"{industry_short} companies that buy {offering_short} in {region_str}"
            )
        else:
            exa_queries.append(
                f"{industry_short} companies in {region_str} {kw['size_hint']}"
            )
    # Add tech/transformation queries without region filter for broader coverage
    if kw["tech_signals"]:
        exa_queries.append(
            f"{industry_short} companies using {', '.join(kw['tech_signals'][:3])}"
        )
    if kw["sub_verticals"]:
        exa_queries.append(
            f"{' '.join(kw['sub_verticals'][:2])} companies {kw['size_hint']}"
        )

    # Format zone summary for the prompt
    zone_summary = "\n".join(
        f"  Zone {i+1}: {z['name']} — {', '.join(z['countries'])} (target: {per_zone_target}+ companies)"
        for i, z in enumerate(zones)
    )

    return f"""Discover companies matching this Ideal Customer Profile. You MUST find at least {max_companies} qualifying companies.

FULL ICP PROFILE (score against ALL dimensions):
{icp_text}

═══════════════════════════════════════════
CRITICAL: GEOGRAPHIC DIVERSITY MANDATE
═══════════════════════════════════════════
The ICP targets {num_zones} geographic zones. You MUST search ALL zones and return
results from EACH zone. Do NOT concentrate results in a single country.

{zone_summary}

RULE: Final results MUST include companies from at least {min(num_zones, 3)} different zones.
If a zone returns fewer results, make ADDITIONAL calls targeting that zone specifically.

═══════════════════════════════════════════
MULTI-SOURCE DISCOVERY STRATEGY
═══════════════════════════════════════════

STEP 1 — Apollo Database Search (PRIMARY, {len(apollo_calls)} calls):
  Make SEPARATE calls per geographic zone so every region gets coverage.
{chr(10).join(apollo_calls)}

STEP 2 — Exa Semantic Search (PRIMARY, {len(exa_queries)} calls):
  Use exa_search with natural language queries, category="company", num_results=15.
  IMPORTANT: Include region-specific queries for EACH geographic zone.
  Suggested queries (adapt as needed):
{chr(10).join(f'    - "{q}"' for q in exa_queries)}

STEP 3 — Broad Web Discovery (SECONDARY, 1-2 calls):
  Use discover_icp_companies with:
    industry_keywords: {json.dumps(kw['industry_keywords'])}
    regions: {json.dumps(kw['regions'][:6])}
    company_size_hint: "{kw['size_hint']}"
    additional_terms: {json.dumps(kw['offering_terms'][:3] + kw['tech_signals'][:2])}
    min_employees: {kw['emp_min']}
    max_employees: {kw['emp_max']}
    min_revenue_usd: {kw['rev_min']}
    max_revenue_usd: {kw['rev_max']}

STEP 4 — Niche Sources (if under {max_companies} qualifying companies):
  search_yc_companies, tavily_search, duckduckgo_search for niche verticals.

STEP 5 — Gap-Fill for Under-Represented Zones:
  After Steps 1-4, check which zones have fewer than {per_zone_target} companies.
  Make targeted calls for those zones:
  - Apollo with locations restricted to the under-represented zone
  - Exa with region-specific queries (e.g., "medical device companies in Germany")
  - duckduckgo_search with region + industry keywords

STEP 6 — Selective Verification (top 10-15 candidates):
  scrape_webpage on /about, /technology, /careers pages to verify:
  - Tech maturity signals: {json.dumps(kw['tech_signals'][:5])}
  - Infrastructure indicators: {json.dumps(kw['infra_indicators'][:5])}
  - Transformation signals: {json.dumps(kw['transformation_keywords'][:5])}

NEGATIVE SIGNAL CHECK:
  Companies showing any of these score 0 on Technology Maturity: {json.dumps(kw['negative_signals'])}

MINIMUM TOOL USAGE: You MUST call at least 3 different tool types (e.g. apollo + exa + discover_icp_companies).

AFTER DISCOVERY: Score each company on all 9 ICP dimensions, classify by evidence strength,
and return the JSON as specified in your system prompt.{_build_strictness_override(options.get("match_strictness", "moderate"))}"""


def build_contact_prompt(company: dict, icp: dict) -> str:
    """Build prompt for Phase 2 — contact discovery for a single company."""
    lt = icp.get("leadership_traits") or icp.get("leadership")
    target_roles = lt.get("target_roles", ["CEO", "CTO", "COO", "VP Engineering"]) if lt else ["CEO", "CTO", "COO", "VP Engineering"]

    # Get industry hint for find_company_executives
    industry = icp.get("industry_types") or icp.get("industry")
    industry_hint = ""
    if industry and isinstance(industry, list) and len(industry) > 0:
        first = industry[0]
        industry_hint = first.get("vertical", "") if isinstance(first, dict) else str(first)

    name = company.get("name", "Unknown")
    domain = company.get("website", "unknown")
    icp_score = company.get("icp_match_score", "N/A")
    qualification = company.get("qualification", "N/A")

    return f"""Research the following company and find decision-maker contacts.

COMPANY: {name}
DOMAIN: {domain}
ICP MATCH SCORE: {icp_score}
QUALIFICATION TIER: {qualification}

TARGET ROLES TO FIND: {', '.join(target_roles)}
INDUSTRY HINT (for find_company_executives): "{industry_hint}"

MANDATORY STEPS:
1. Call research_company("{name}", "{domain}", target_roles={json.dumps(target_roles)})
2. Call find_company_executives("{name}", "{domain}", target_roles={json.dumps(target_roles)}, industry_hint="{industry_hint}")
3. Merge contacts from both tools (deduplicate by LinkedIn URL or full name).
4. Include inferred_emails from find_company_executives with confidence=0.4.
5. Collect all research_data (financials, news, tech_signals) for downstream BANT scoring.

Return the JSON output as specified in your system prompt."""


def build_bant_prompt(company_with_research: dict, icp: dict) -> str:
    """Build prompt for Phase 3 — BANT scoring for a single company.

    Args:
        company_with_research: Company dict with contacts and research_data from Phase 2.
        icp: The ICP config dict.
    """
    name = company_with_research.get("name", "Unknown")
    domain = company_with_research.get("website", "unknown")

    # Format contacts summary for context
    contacts = company_with_research.get("contacts", [])
    contacts_summary = []
    for c in contacts[:5]:
        role = c.get("designation") or c.get("role_category") or "Unknown role"
        contact_name = c.get("full_name") or "Unknown"
        contacts_summary.append(f"  - {contact_name}: {role}")
    contacts_text = "\n".join(contacts_summary) if contacts_summary else "  No contacts found"

    # Format research data
    research_data = company_with_research.get("research_data", {})
    financials = research_data.get("financials", "No financial data gathered")
    news = research_data.get("news", "No news data gathered")
    tech_signals = research_data.get("tech_signals", [])
    source_urls = research_data.get("source_urls", [])

    source_urls_text = ""
    if source_urls:
        for s in source_urls[:10]:
            source_urls_text += f"  - [{s.get('title', 'Untitled')}]({s.get('url', '')}) (via {s.get('tool', 'unknown')})\n"
    else:
        source_urls_text = "  No source URLs gathered\n"

    # ICP context for need scoring
    icp_text = _format_icp_sections(icp)

    return f"""Score the following company using the BANT framework. Use the pre-gathered research data first,
and only call tools to fill significant gaps.

COMPANY: {name}
DOMAIN: {domain}

IDENTIFIED CONTACTS:
{contacts_text}

PRE-GATHERED RESEARCH DATA:
  Financials: {financials}
  News: {news}
  Tech Signals: {json.dumps(tech_signals)}

SOURCE URLs FROM PRIOR RESEARCH:
{source_urls_text}
ICP CONTEXT (for Need scoring):
{icp_text}

Score each BANT dimension 1-5 with evidence. Cite the source URLs above where possible.
Only call tools if research_data has significant gaps for a dimension.
Return the JSON output as specified in your system prompt."""
