"""Industry-specific search query strategies.

Maps industry verticals to high-yield query patterns: industry associations,
regulatory filings, award lists, directory sites, and geographic clusters.
Used by icp_discovery_tool and prompt_builder to generate targeted queries.
"""

from datetime import datetime

# Each strategy includes:
# - association_queries: Industry associations and member directories
# - regulatory_queries: Regulatory filings and approvals
# - award_queries: Industry award lists and rankings
# - directory_queries: Industry-specific directory sites
# - cluster_queries: Geographic hub searches

INDUSTRY_STRATEGIES: dict[str, dict] = {
    "medical device": {
        "association_queries": [
            "AdvaMed member companies list",
            "MDMA Medical Device Manufacturers Association members",
            "MedTech Europe member companies",
            "RAPS member directory medical device",
        ],
        "regulatory_queries": [
            "FDA 510(k) cleared companies {year}",
            "FDA PMA approved medical device {year}",
            "CE marked medical device companies Europe",
            "FDA warning letter medical device {year}",
        ],
        "award_queries": [
            "Medical Device and Diagnostics Industry Awards {year}",
            "Medtech Innovator top companies {year}",
            "Prix Galien medical device winners",
        ],
        "directory_queries": [
            "site:medicaldesignandoutsourcing.com company profile",
            "site:massdevice.com company",
            "site:devicetechsolutions.com manufacturer",
        ],
        "cluster_queries": [
            "medical device companies Minneapolis",
            "medtech hub Boston companies",
            "medical device corridor Orange County companies",
            "medical device Galway Ireland companies",
        ],
    },
    "healthcare": {
        "association_queries": [
            "HIMSS member companies health IT",
            "AHA American Hospital Association partners",
            "CHIME member companies health informatics",
        ],
        "regulatory_queries": [
            "HIPAA compliant technology vendors list",
            "ONC certified health IT vendors {year}",
        ],
        "award_queries": [
            "Healthcare Informatics HCI 100 {year}",
            "Digital Health 150 CB Insights {year}",
            "Rock Health funded companies {year}",
        ],
        "directory_queries": [
            "site:healthcareitnews.com vendor",
            "site:chiefhealthcareexecutive.com company",
        ],
        "cluster_queries": [
            "health tech companies Nashville",
            "healthcare startup hub Boston companies",
            "digital health companies San Francisco Bay Area",
        ],
    },
    "pharmaceutical": {
        "association_queries": [
            "PhRMA member companies list",
            "EFPIA member companies Europe pharmaceutical",
            "BIO member company biotechnology",
        ],
        "regulatory_queries": [
            "FDA NDA approved drugs {year} company",
            "EMA marketing authorization {year} company",
            "FDA breakthrough therapy designation {year}",
        ],
        "award_queries": [
            "Fierce Pharma top pharmaceutical companies {year}",
            "BioPharma Dive company {year}",
            "Endpoints 100 top biotech {year}",
        ],
        "directory_queries": [
            "site:fiercepharma.com company",
            "site:pharmamanufacturing.com company",
        ],
        "cluster_queries": [
            "pharmaceutical companies New Jersey corridor",
            "biotech companies Cambridge Massachusetts",
            "pharma companies Basel Switzerland",
        ],
    },
    "software": {
        "association_queries": [
            "BSA Software Alliance member companies",
            "SaaStr top SaaS companies",
            "SaaS 1000 fastest growing",
        ],
        "regulatory_queries": [],
        "award_queries": [
            "Deloitte Technology Fast 500 {year}",
            "Inc 5000 software companies {year}",
            "Forbes Cloud 100 {year}",
            "G2 best software products {year}",
        ],
        "directory_queries": [
            "site:g2.com/products company",
            "site:capterra.com software vendor",
            "site:trustradius.com vendor",
        ],
        "cluster_queries": [
            "software companies Silicon Valley",
            "SaaS companies Austin Texas",
            "tech companies Seattle Bellevue",
            "software hub Berlin companies",
        ],
    },
    "saas": {
        "association_queries": [
            "SaaStr top SaaS companies list",
            "SaaS 1000 fastest growing",
        ],
        "regulatory_queries": [],
        "award_queries": [
            "Forbes Cloud 100 {year}",
            "SaaS Awards winners {year}",
            "Bessemer cloud index companies",
            "G2 best software {year}",
        ],
        "directory_queries": [
            "site:g2.com/products company",
            "site:getlatka.com company revenue",
        ],
        "cluster_queries": [
            "SaaS companies San Francisco",
            "B2B SaaS startups New York",
            "SaaS companies Dublin Ireland",
        ],
    },
    "fintech": {
        "association_queries": [
            "Innovate Finance member companies",
            "Electronic Transactions Association member list",
        ],
        "regulatory_queries": [
            "OCC fintech charter approved companies",
            "FCA regulated fintech companies UK",
        ],
        "award_queries": [
            "Forbes Fintech 50 {year}",
            "CB Insights Fintech 250 {year}",
            "Fintech Innovation Awards {year}",
        ],
        "directory_queries": [
            "site:fintechmagazine.com company",
            "site:thefinanser.com company",
        ],
        "cluster_queries": [
            "fintech companies London",
            "fintech hub Singapore companies",
            "fintech startups New York",
        ],
    },
    "cybersecurity": {
        "association_queries": [
            "Cybersecurity Ventures top companies",
            "CISA trusted vendors list",
        ],
        "regulatory_queries": [
            "FedRAMP authorized vendors list",
            "CMMC certified companies list",
        ],
        "award_queries": [
            "Cybersecurity Excellence Awards {year}",
            "Gartner Magic Quadrant cybersecurity {year}",
            "SC Media awards cybersecurity {year}",
        ],
        "directory_queries": [
            "site:crn.com cybersecurity company",
            "site:darkreading.com vendor",
        ],
        "cluster_queries": [
            "cybersecurity companies Washington DC",
            "cybersecurity hub Tel Aviv companies",
            "cybersecurity companies Boston",
        ],
    },
    "manufacturing": {
        "association_queries": [
            "NAM National Association of Manufacturers members",
            "SME manufacturing member companies",
        ],
        "regulatory_queries": [
            "ISO 9001 certified manufacturers {region}",
            "AS9100 certified aerospace manufacturers",
        ],
        "award_queries": [
            "IndustryWeek Best Plants {year}",
            "Manufacturing Leadership Awards {year}",
        ],
        "directory_queries": [
            "site:thomasnet.com manufacturer",
            "site:industrynet.com manufacturer",
        ],
        "cluster_queries": [
            "manufacturing companies Midwest USA",
            "precision manufacturing companies Germany",
            "contract manufacturer companies Shenzhen",
        ],
    },
    "energy": {
        "association_queries": [
            "American Petroleum Institute member companies",
            "Solar Energy Industries Association members",
            "AWEA American Wind Energy members",
        ],
        "regulatory_queries": [
            "FERC licensed energy companies",
            "DOE grant recipients energy {year}",
        ],
        "award_queries": [
            "Cleantech 100 companies {year}",
            "Bloomberg New Energy Finance top {year}",
        ],
        "directory_queries": [
            "site:energycentral.com company",
            "site:renewableenergyworld.com company",
        ],
        "cluster_queries": [
            "energy companies Houston Texas",
            "renewable energy companies Denmark",
            "solar companies California",
        ],
    },
    "automotive": {
        "association_queries": [
            "OICA automotive manufacturers members",
            "SAE International member companies",
            "MEMA motor equipment manufacturers",
        ],
        "regulatory_queries": [
            "NHTSA registered motor vehicle manufacturers",
        ],
        "award_queries": [
            "Automotive News top suppliers {year}",
            "Ward's Auto best engines {year}",
        ],
        "directory_queries": [
            "site:autonews.com supplier",
            "site:just-auto.com company",
        ],
        "cluster_queries": [
            "automotive companies Detroit Michigan",
            "auto parts suppliers Stuttgart Germany",
            "automotive companies Nagoya Japan",
        ],
    },
}

# ──────────────────────────────────────────────────────────────────
# Industry synonym expansion
# ──────────────────────────────────────────────────────────────────

INDUSTRY_SYNONYMS: dict[str, list[str]] = {
    "medical device": ["medtech", "medical equipment", "health tech devices", "biomedical devices", "diagnostic equipment"],
    "healthcare": ["health tech", "digital health", "health services", "health informatics", "telehealth"],
    "pharmaceutical": ["pharma", "biopharma", "drug development", "life sciences", "biotech"],
    "software": ["software development", "tech companies", "IT solutions", "software products", "application software"],
    "saas": ["cloud software", "software-as-a-service", "cloud platform", "subscription software", "B2B SaaS"],
    "fintech": ["financial technology", "digital payments", "neobank", "insurtech", "regtech"],
    "cybersecurity": ["infosec", "information security", "network security", "cyber defense", "security software"],
    "manufacturing": ["industrial manufacturing", "contract manufacturing", "precision manufacturing", "OEM", "fabrication"],
    "energy": ["cleantech", "renewable energy", "energy technology", "power generation", "clean energy"],
    "automotive": ["auto industry", "vehicle manufacturing", "mobility", "EV companies", "automotive technology"],
    "aerospace": ["aerospace & defense", "aviation", "space technology", "defense contractor", "satellite"],
    "artificial intelligence": ["AI companies", "machine learning", "deep learning", "AI/ML", "generative AI"],
    "ecommerce": ["e-commerce", "online retail", "digital commerce", "marketplace", "D2C brands"],
    "construction": ["building technology", "construction tech", "contech", "civil engineering", "infrastructure"],
    "logistics": ["supply chain", "freight tech", "transportation", "warehousing", "last-mile delivery"],
}


def expand_industry_keywords(keywords: list[str]) -> list[str]:
    """Expand industry keywords with synonyms for broader query coverage.

    Returns the union of original keywords + matched synonyms.
    Preserves order: originals first, then synonyms.
    """
    expanded = list(keywords)
    seen = {k.lower().strip() for k in keywords}

    for kw in keywords:
        kw_lower = kw.lower().strip()
        # Exact match
        if kw_lower in INDUSTRY_SYNONYMS:
            for syn in INDUSTRY_SYNONYMS[kw_lower]:
                if syn.lower() not in seen:
                    expanded.append(syn)
                    seen.add(syn.lower())
            continue
        # Partial match
        for key, synonyms in INDUSTRY_SYNONYMS.items():
            if key in kw_lower or kw_lower in key:
                for syn in synonyms:
                    if syn.lower() not in seen:
                        expanded.append(syn)
                        seen.add(syn.lower())
                break

    return expanded


# Default strategy for industries not in the map
DEFAULT_STRATEGY = {
    "association_queries": [],
    "regulatory_queries": [],
    "award_queries": [
        "Deloitte Technology Fast 500 {year}",
        "Inc 5000 fastest growing companies {year}",
    ],
    "directory_queries": [
        "site:crunchbase.com company",
        "site:owler.com company",
    ],
    "cluster_queries": [],
}


def get_industry_queries(
    industry_keywords: list[str],
    regions: list[str] = None,
    max_queries: int = 15,
) -> list[str]:
    """Generate industry-specific search queries for company discovery.

    Args:
        industry_keywords: Industry terms from the ICP (e.g. ["medical device"])
        regions: Target countries/regions
        max_queries: Maximum number of queries to return

    Returns:
        List of search query strings optimized for the industry
    """
    regions = regions or []
    current_year = datetime.now().year
    last_year = current_year - 1

    queries = []

    # Find matching strategy
    strategy = DEFAULT_STRATEGY
    for keyword in industry_keywords:
        kw_lower = keyword.lower().strip()
        if kw_lower in INDUSTRY_STRATEGIES:
            strategy = INDUSTRY_STRATEGIES[kw_lower]
            break
        # Partial match
        for key in INDUSTRY_STRATEGIES:
            if key in kw_lower or kw_lower in key:
                strategy = INDUSTRY_STRATEGIES[key]
                break
        if strategy != DEFAULT_STRATEGY:
            break

    # Add association queries
    for q in strategy.get("association_queries", []):
        queries.append(q.format(year=current_year, region=regions[0] if regions else ""))

    # Add regulatory queries (with year substitution)
    for q in strategy.get("regulatory_queries", []):
        queries.append(q.format(year=current_year, region=regions[0] if regions else ""))
        if "{year}" in q:
            queries.append(q.format(year=last_year, region=regions[0] if regions else ""))

    # Add award/ranking queries
    for q in strategy.get("award_queries", []):
        queries.append(q.format(year=current_year))

    # Add directory site searches
    for q in strategy.get("directory_queries", []):
        for kw in industry_keywords[:2]:
            queries.append(f"{q} {kw}")

    # Add geographic cluster queries
    cluster_queries = strategy.get("cluster_queries", [])
    if not cluster_queries and regions:
        # Generate generic cluster queries
        for kw in industry_keywords[:2]:
            for region in regions[:2]:
                queries.append(f"{kw} companies {region}")
    else:
        queries.extend(cluster_queries)

    # Add region-specific queries if regions provided
    for kw in industry_keywords[:2]:
        for region in regions[:3]:
            queries.append(f"top {kw} companies {region} {current_year}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)

    return unique[:max_queries]


def get_strategy_summary(industry_keywords: list[str]) -> dict:
    """Return a summary of the query strategy for an industry.

    Useful for including in agent prompts to suggest high-yield queries.
    """
    for keyword in industry_keywords:
        kw_lower = keyword.lower().strip()
        if kw_lower in INDUSTRY_STRATEGIES:
            return {
                "industry": kw_lower,
                "matched": True,
                "strategy": INDUSTRY_STRATEGIES[kw_lower],
            }
        for key in INDUSTRY_STRATEGIES:
            if key in kw_lower or kw_lower in key:
                return {
                    "industry": key,
                    "matched": True,
                    "strategy": INDUSTRY_STRATEGIES[key],
                }

    return {
        "industry": industry_keywords[0] if industry_keywords else "unknown",
        "matched": False,
        "strategy": DEFAULT_STRATEGY,
    }
