"""Wikidata SPARQL company discovery tool.

Queries the Wikidata SPARQL endpoint to find companies by industry
and geography. Returns structured data including name, website,
employee count, revenue, founding date, headquarters, and stock ticker.

Completely free, no API key, no rate limits for reasonable usage.
Particularly strong for Fortune 500/Global 2000 companies.
"""

import logging
from urllib.parse import quote

from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Map common industry terms to Wikidata industry class QIDs
INDUSTRY_QID_MAP = {
    "medical device": "Q913142",
    "medtech": "Q913142",
    "healthcare": "Q31207",
    "pharmaceutical": "Q507443",
    "biotechnology": "Q206473",
    "software": "Q7397",
    "information technology": "Q11661",
    "artificial intelligence": "Q11660",
    "cybersecurity": "Q3510521",
    "fintech": "Q5453832",
    "financial services": "Q837171",
    "banking": "Q22687",
    "insurance": "Q43183",
    "automotive": "Q190117",
    "aerospace": "Q8065",
    "defense": "Q1142706",
    "energy": "Q11451",
    "renewable energy": "Q12705",
    "oil and gas": "Q862571",
    "mining": "Q44497",
    "construction": "Q385378",
    "real estate": "Q10538",
    "retail": "Q126793",
    "e-commerce": "Q484954",
    "food and beverage": "Q2095",
    "agriculture": "Q11451",
    "telecommunications": "Q418",
    "media": "Q11033",
    "entertainment": "Q173799",
    "gaming": "Q941594",
    "education": "Q8434",
    "logistics": "Q177777",
    "manufacturing": "Q187939",
    "chemical": "Q207652",
    "consulting": "Q268592",
    "saas": "Q1254596",
    "cloud computing": "Q483639",
    "semiconductor": "Q161428",
    "robotics": "Q11012",
}

# Map country names to Wikidata country QIDs
COUNTRY_QID_MAP = {
    "usa": "Q30", "united states": "Q30", "us": "Q30",
    "uk": "Q145", "united kingdom": "Q145", "great britain": "Q145",
    "germany": "Q183", "deutschland": "Q183",
    "france": "Q142",
    "canada": "Q16",
    "australia": "Q408",
    "japan": "Q17",
    "india": "Q668",
    "china": "Q148",
    "south korea": "Q884", "korea": "Q884",
    "brazil": "Q155",
    "israel": "Q801",
    "switzerland": "Q39",
    "netherlands": "Q55",
    "sweden": "Q34",
    "singapore": "Q334",
    "ireland": "Q27",
    "italy": "Q38",
    "spain": "Q29",
    "norway": "Q20",
    "denmark": "Q35",
    "finland": "Q33",
    "austria": "Q40",
    "belgium": "Q31",
    "new zealand": "Q664",
    "mexico": "Q96",
    "uae": "Q878", "united arab emirates": "Q878",
    "saudi arabia": "Q851",
    "taiwan": "Q865",
    "poland": "Q36",
}


def _find_industry_qid(keyword: str) -> str | None:
    """Find the best matching Wikidata QID for an industry keyword."""
    kw = keyword.lower().strip()
    if kw in INDUSTRY_QID_MAP:
        return INDUSTRY_QID_MAP[kw]
    # Partial match
    for key, qid in INDUSTRY_QID_MAP.items():
        if key in kw or kw in key:
            return qid
    return None


def _find_country_qid(country: str) -> str | None:
    """Find the Wikidata QID for a country name."""
    c = country.lower().strip()
    return COUNTRY_QID_MAP.get(c)


def _build_sparql_query(
    industry_keywords: list[str],
    countries: list[str],
    limit: int = 500,
) -> str:
    """Build a SPARQL query for company discovery.

    Strategy: Find instances of Q4830453 (business enterprise) or Q783794 (company)
    that are in the specified industry and optionally headquartered in specific countries.
    """
    # Build industry filter
    industry_qids = []
    for kw in industry_keywords:
        qid = _find_industry_qid(kw)
        if qid:
            industry_qids.append(qid)

    # Build country filter
    country_qids = []
    for country in countries:
        qid = _find_country_qid(country)
        if qid:
            country_qids.append(qid)

    # Build SPARQL
    industry_values = " ".join(f"wd:{qid}" for qid in industry_qids) if industry_qids else ""
    country_values = " ".join(f"wd:{qid}" for qid in country_qids) if country_qids else ""

    industry_filter = f"VALUES ?industry {{ {industry_values} }}\n  ?company wdt:P452 ?industry ." if industry_values else ""
    country_filter = f"VALUES ?hqCountry {{ {country_values} }}\n  ?company wdt:P159/wdt:P17 ?hqCountry ." if country_values else ""

    # If no industry QIDs found, fall back to text search on description
    if not industry_qids:
        keyword_text = " ".join(industry_keywords[:3])
        industry_filter = f'?company schema:description ?desc . FILTER(LANG(?desc) = "en") FILTER(CONTAINS(LCASE(?desc), "{keyword_text.lower()}"))'

    query = f"""SELECT DISTINCT ?company ?companyLabel ?website ?employeeCount ?revenue
  ?foundingDate ?hqLabel ?stockTicker ?parentLabel
WHERE {{
  {{ ?company wdt:P31/wdt:P279* wd:Q4830453 . }}
  UNION
  {{ ?company wdt:P31/wdt:P279* wd:Q783794 . }}

  {industry_filter}
  {country_filter}

  OPTIONAL {{ ?company wdt:P856 ?website . }}
  OPTIONAL {{ ?company wdt:P1128 ?employeeCount . }}
  OPTIONAL {{ ?company wdt:P2139 ?revenue . }}
  OPTIONAL {{ ?company wdt:P571 ?foundingDate . }}
  OPTIONAL {{ ?company wdt:P159 ?hq . ?hq rdfs:label ?hqLabel . FILTER(LANG(?hqLabel) = "en") }}
  OPTIONAL {{ ?company wdt:P414 ?exchange . ?company wdt:P249 ?stockTicker . }}
  OPTIONAL {{ ?company wdt:P749 ?parent . ?parent rdfs:label ?parentLabel . FILTER(LANG(?parentLabel) = "en") }}

  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT {limit}"""
    return query


@tool
def search_wikidata_companies(
    industry_keywords: list[str],
    countries: list[str] = None,
    limit: int = 500,
) -> dict:
    """
    Search Wikidata for companies by industry and geography.
    FREE, no API key required, no rate limits for reasonable usage.
    Returns structured data including name, website, employee count,
    revenue, founding date, headquarters, and stock ticker.

    Particularly strong for established/large companies (Fortune 500,
    Global 2000). Less effective for small startups.

    USE IN STAGES: Stage 1 (Industry Discovery) as a primary data source.

    Args:
        industry_keywords: Industry terms to search for (e.g. ["medical device",
            "healthcare technology"]). Maps to Wikidata industry classifications.
        countries: Optional list of countries to filter by (e.g. ["USA", "Germany"]).
            Leave empty for global search.
        limit: Maximum number of results (default 500).

    Returns:
        dict with 'companies' list, 'total_found' count, and 'query_info'
    """
    countries = countries or []

    query = _build_sparql_query(industry_keywords, countries, limit)

    try:
        response = httpx_get_with_retry(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "json"},
            headers={
                "User-Agent": "qlGen/1.0 (Lead Generation Research Tool)",
                "Accept": "application/sparql-results+json",
            },
            timeout=30,
        )

        if response.status_code != 200:
            return {
                "error": f"Wikidata SPARQL returned HTTP {response.status_code}",
                "companies": [],
                "total_found": 0,
            }

        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])

        # Parse results
        companies_by_uri: dict[str, dict] = {}
        for binding in bindings:
            uri = binding.get("company", {}).get("value", "")
            if not uri:
                continue

            if uri not in companies_by_uri:
                name = binding.get("companyLabel", {}).get("value", "")
                # Skip if name is just a QID (means no English label exists)
                if name.startswith("Q") and name[1:].isdigit():
                    continue

                website_raw = binding.get("website", {}).get("value", "")
                website = ""
                if website_raw:
                    # Extract domain from full URL
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(website_raw)
                        domain = parsed.netloc.lower()
                        if domain.startswith("www."):
                            domain = domain[4:]
                        website = domain
                    except Exception:
                        website = website_raw

                employee_count = None
                emp_val = binding.get("employeeCount", {}).get("value")
                if emp_val:
                    try:
                        employee_count = int(float(emp_val))
                    except (ValueError, TypeError):
                        pass

                revenue = None
                rev_val = binding.get("revenue", {}).get("value")
                if rev_val:
                    try:
                        revenue = int(float(rev_val))
                    except (ValueError, TypeError):
                        pass

                founding_date = binding.get("foundingDate", {}).get("value", "")
                if founding_date and "T" in founding_date:
                    founding_date = founding_date.split("T")[0]

                headquarters = binding.get("hqLabel", {}).get("value", "")
                stock_ticker = binding.get("stockTicker", {}).get("value", "")
                parent_company = binding.get("parentLabel", {}).get("value", "")

                companies_by_uri[uri] = {
                    "name": name,
                    "website": website,
                    "employee_count": employee_count,
                    "revenue_estimate": revenue,
                    "founding_date": founding_date,
                    "headquarters": headquarters,
                    "stock_ticker": stock_ticker,
                    "parent_company": parent_company,
                    "source": "wikidata",
                    "wikidata_uri": uri,
                }

        companies = list(companies_by_uri.values())

        # Sort by those with most data first
        companies.sort(
            key=lambda c: sum(1 for v in c.values() if v),
            reverse=True,
        )

        logger.info(
            f"Wikidata: found {len(companies)} companies for "
            f"industries={industry_keywords}, countries={countries}"
        )

        return {
            "companies": companies,
            "total_found": len(companies),
            "query_info": {
                "industry_keywords": industry_keywords,
                "countries": countries,
                "industry_qids_matched": [
                    _find_industry_qid(kw) for kw in industry_keywords
                    if _find_industry_qid(kw)
                ],
            },
        }

    except Exception as e:
        logger.error(f"Wikidata search failed: {e}")
        return {
            "error": str(e),
            "companies": [],
            "total_found": 0,
        }
