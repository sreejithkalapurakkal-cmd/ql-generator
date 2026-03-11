"""Batch ICP company discovery tool.

Runs 15-20 DuckDuckGo searches internally with varied query patterns,
scrapes industry directory pages, and returns a compiled deduplicated
list of companies matching ICP criteria — all in a single tool call.
"""

import re
import logging
import time
from urllib.parse import urlparse

import httpx
from strands import tool

logger = logging.getLogger(__name__)

# Domains to skip — search engines, social media, generic sites
SKIP_DOMAINS = {
    "google.com", "youtube.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "reddit.com", "wikipedia.org", "amazon.com",
    "linkedin.com", "pinterest.com", "tiktok.com", "yelp.com",
    "glassdoor.com", "indeed.com", "bbb.org", "gov", "edu",
}

# Domains that are directories/lists (scrape these for company names)
DIRECTORY_KEYWORDS = [
    "list", "top", "best", "directory", "companies", "ranking",
    "guide", "review", "comparison", "award", "winner", "member",
]


def _is_company_domain(domain: str) -> bool:
    """Check if a domain likely belongs to a company (not a directory/news site)."""
    for skip in SKIP_DOMAINS:
        if domain.endswith(skip):
            return False
    return True


def _extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _is_directory_page(title: str, body: str) -> bool:
    """Check if a search result is likely a directory/list page."""
    text = (title + " " + body).lower()
    return sum(1 for kw in DIRECTORY_KEYWORDS if kw in text) >= 2


def _scrape_companies_from_page(url: str) -> list[dict]:
    """Scrape a directory/list page for company names and websites."""
    companies = []
    try:
        from bs4 import BeautifulSoup

        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 qlGen Research Bot"},
        )
        if response.status_code != 200:
            return companies

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        # Look for links that point to company websites
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href.startswith("http"):
                continue
            domain = _extract_domain(href)
            if not domain or not _is_company_domain(domain):
                continue

            name = a.get_text(strip=True)
            if name and len(name) > 2 and len(name) < 100:
                companies.append({
                    "name": name,
                    "website": domain,
                    "source_url": url,
                })

        # Also extract text that looks like company names near keywords
        text = soup.get_text(separator="\n", strip=True)
        # Look for lines that are short and capitalized (likely company names)
        for line in text.split("\n"):
            line = line.strip()
            if 3 < len(line) < 60 and not line.startswith("http"):
                # Simple heuristic: mostly title case or uppercase
                if line[0].isupper() and any(c.islower() for c in line):
                    # Could be a company name; skip common non-company patterns
                    if not any(kw in line.lower() for kw in ["cookie", "privacy", "terms", "copyright", "sign up", "log in", "menu"]):
                        companies.append({
                            "name": line,
                            "website": None,
                            "source_url": url,
                        })

    except Exception as e:
        logger.debug(f"Failed to scrape {url}: {e}")

    return companies[:30]  # Cap per page


def _extract_size_signals(text: str) -> dict:
    """Extract employee count and revenue mentions from a text snippet."""
    signals = {"employee_mentions": [], "revenue_mentions": []}
    text_lower = text.lower()

    # Employee count patterns: "250 employees", "~500 staff", "50-200 people"
    emp_patterns = re.findall(
        r"(\d[\d,]*)\s*(?:employees?|staff|people|team members|headcount|full[- ]?time)",
        text_lower,
    )
    for p in emp_patterns[:3]:
        try:
            signals["employee_mentions"].append(int(p.replace(",", "")))
        except ValueError:
            pass

    # Revenue patterns: "$25M", "$10 million", "30M revenue"
    rev_patterns = re.findall(
        r"\$\s*(\d[\d,.]*)\s*(million|m\b|billion|b\b)|(\d[\d,.]*)\s*(million|m\b)\s*(?:revenue|ARR|sales)",
        text_lower,
    )
    for match in rev_patterns[:3]:
        try:
            num_str = (match[0] or match[2]).replace(",", "")
            unit = (match[1] or match[3]).lower()
            num = float(num_str)
            if "billion" in unit or unit == "b":
                num *= 1_000_000_000
            else:
                num *= 1_000_000
            signals["revenue_mentions"].append(int(num))
        except (ValueError, IndexError):
            pass

    return signals


def _size_label(min_emp: int, max_emp: int) -> str:
    """Return a human-readable size label for embedding in queries."""
    if not min_emp and not max_emp:
        return ""
    if max_emp and max_emp <= 200:
        return "small startup"
    if max_emp and max_emp <= 800:
        return "mid-size"
    return "growth-stage"


def _revenue_label(min_rev: int, max_rev: int) -> str:
    """Return a human-readable revenue label."""
    if not max_rev:
        return ""
    if max_rev <= 10_000_000:
        return "under $10M revenue"
    if max_rev <= 50_000_000:
        return "$10M-$50M revenue"
    if max_rev <= 200_000_000:
        return "$50M-$200M revenue"
    return "mid-market"


def _generate_queries(
    industry_keywords: list[str],
    regions: list[str],
    company_size_hint: str,
    additional_terms: list[str],
    min_employees: int = None,
    max_employees: int = None,
    min_revenue: int = None,
    max_revenue: int = None,
) -> list[str]:
    """Generate 20-30 varied search queries from ICP criteria.

    Critically: embeds size/revenue constraints directly into queries to avoid
    returning large enterprises when the ICP targets SMBs.
    """
    queries = []
    size_lbl = _size_label(min_employees, max_employees) if (min_employees or max_employees) else (company_size_hint or "")
    rev_lbl = _revenue_label(min_revenue, max_revenue) if (min_revenue or max_revenue) else ""

    # Pattern 1: Industry + size + region  ← MOST IMPORTANT for size-correct results
    for kw in industry_keywords[:4]:
        if size_lbl:
            queries.append(f"{size_lbl} {kw} company")
        for region in regions[:3]:
            if size_lbl:
                queries.append(f"{size_lbl} {kw} company {region}")
            else:
                queries.append(f"{kw} companies in {region}")

    # Pattern 2: Funding-stage proxies (Series A/B = $10M-$50M range)
    for kw in industry_keywords[:3]:
        if max_revenue and max_revenue <= 50_000_000:
            queries.append(f"{kw} startup Series A funding")
            queries.append(f"{kw} startup Series B funding")
            queries.append(f"{kw} company venture backed")
        elif max_employees and max_employees <= 500:
            queries.append(f"{kw} startup 100 employees")
            queries.append(f"{kw} company growth stage")
        else:
            queries.append(f"{kw} companies funding round 2024 2025")

    # Pattern 3: Employee count in query
    if min_employees and max_employees:
        for kw in industry_keywords[:2]:
            queries.append(f"{kw} company {min_employees}-{max_employees} employees")

    # Pattern 4: Revenue in query
    if rev_lbl:
        for kw in industry_keywords[:2]:
            queries.append(f"{kw} company {rev_lbl}")

    # Pattern 5: Directories + associations
    for kw in industry_keywords[:3]:
        queries.append(f"{kw} company directory startup list")
        queries.append(f"{kw} companies site:crunchbase.com")
        queries.append(f"{kw} companies site:pitchbook.com")

    # Pattern 6: Additional/adjacent terms with size
    for term in additional_terms[:4]:
        if size_lbl:
            queries.append(f"{size_lbl} {term} company")
        else:
            queries.append(f"{term} companies")

    # Pattern 7: YC / accelerator companies in this space (tend to be right size)
    for kw in industry_keywords[:2]:
        queries.append(f"Y Combinator {kw} startup")
        queries.append(f"{kw} accelerator portfolio company")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        ql = q.lower().strip()
        if ql not in seen:
            seen.add(ql)
            unique.append(q)

    # Cap at 15 queries to reduce DuckDuckGo rate-limit risk.
    # The most important queries are at the top (industry + size + region).
    return unique[:15]


@tool
def discover_icp_companies(
    industry_keywords: list[str],
    regions: list[str] = None,
    company_size_hint: str = "",
    additional_terms: list[str] = None,
    min_employees: int = None,
    max_employees: int = None,
    min_revenue_usd: int = None,
    max_revenue_usd: int = None,
) -> dict:
    """
    Batch-discover companies matching ICP criteria. Runs up to 15 DuckDuckGo
    searches internally with size-constrained query patterns and scrapes
    directory pages. Returns a compiled, deduplicated list of company candidates.

    NOTE: This tool uses DuckDuckGo which rate-limits automated queries.
    Prefer apollo_company_search and exa_search as primary discovery tools.
    Use this tool as a SECONDARY source — call it 1-2 times max per pipeline run.

    CRITICAL: Pass employee and revenue ranges so searches target the RIGHT SIZE
    companies. Without size constraints the tool returns large enterprises instead
    of the SMBs the ICP targets.

    Args:
        industry_keywords: Core industry terms from ICP (e.g. ["medical device manufacturer",
            "connected health devices", "wearable medical devices"])
        regions: Target countries/regions (e.g. ["USA", "Germany", "UK"])
        company_size_hint: Free-text size description if no numeric range available
        additional_terms: Extra search terms — adjacent verticals, tech keywords
        min_employees: Minimum employee count from ICP (e.g. 50)
        max_employees: Maximum employee count from ICP (e.g. 800)
        min_revenue_usd: Minimum annual revenue in USD (e.g. 10000000)
        max_revenue_usd: Maximum annual revenue in USD (e.g. 30000000)

    Returns:
        dict with 'companies' list (name, website, snippet, source, size_signals),
        'total_found' count, and 'queries_run' count
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return {"error": "ddgs not installed", "companies": [], "total_found": 0}

    regions = regions or []
    additional_terms = additional_terms or []

    queries = _generate_queries(
        industry_keywords, regions, company_size_hint, additional_terms,
        min_employees, max_employees, min_revenue_usd, max_revenue_usd,
    )
    logger.info(f"ICP Discovery: running {len(queries)} queries")

    # Collect companies: domain -> best info
    companies_by_domain: dict[str, dict] = {}
    companies_by_name: dict[str, dict] = {}
    directory_urls = []

    try:
        from ddgs.exceptions import RatelimitException
    except ImportError:
        RatelimitException = Exception  # Fallback

    consecutive_failures = 0
    rate_limited = False
    for i, query in enumerate(queries):
        if rate_limited:
            # Stop making DDG calls once rate-limited — remaining queries won't help
            logger.info(f"ICP Discovery: skipping remaining {len(queries) - i} queries (rate limited)")
            break

        if i > 0:
            # Base delay of 4s between queries, increasing by 3s per consecutive failure.
            # DDG detects automated patterns; spacing calls out is the primary defense.
            delay = 4 + (consecutive_failures * 3)
            time.sleep(min(delay, 20))

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))
            consecutive_failures = 0  # Reset on success
        except RatelimitException:
            rate_limited = True
            logger.warning(f"DDG rate limited after {i} queries. Stopping DDG calls.")
            continue
        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"DDG query failed ({consecutive_failures}x): {query} — {e}")
            if consecutive_failures >= 3:
                rate_limited = True
                logger.warning("DDG repeatedly failing, treating as rate limited. Stopping.")
            continue

        for r in results:
            href = r.get("href", "")
            title = r.get("title", "")
            body = r.get("body", "")
            domain = _extract_domain(href)

            # Check if this is a directory page worth scraping
            if _is_directory_page(title, body):
                directory_urls.append(href)

            # Check if this is a company website
            if domain and _is_company_domain(domain):
                if domain not in companies_by_domain:
                    # Try to extract company name from title
                    name = title.split(" - ")[0].split(" | ")[0].split(" — ")[0].strip()
                    if len(name) > 100:
                        name = name[:100]

                    # Extract size signals from snippet
                    size_signals = _extract_size_signals(body)

                    companies_by_domain[domain] = {
                        "name": name,
                        "website": domain,
                        "snippet": body[:200],
                        "source_url": href,
                        "source_query": query,
                        "size_signals": size_signals,
                    }

    # Scrape top directory pages for more companies
    seen_dirs = set()
    for url in directory_urls[:8]:
        domain = _extract_domain(url)
        if domain in seen_dirs:
            continue
        seen_dirs.add(domain)

        time.sleep(1)
        scraped = _scrape_companies_from_page(url)
        for comp in scraped:
            if comp.get("website") and comp["website"] not in companies_by_domain:
                companies_by_domain[comp["website"]] = {
                    "name": comp["name"],
                    "website": comp["website"],
                    "snippet": "",
                    "source_url": comp["source_url"],
                    "source_query": "directory_scrape",
                }
            elif comp.get("name") and comp["name"] not in companies_by_name:
                companies_by_name[comp["name"]] = {
                    "name": comp["name"],
                    "website": None,
                    "snippet": "",
                    "source_url": comp.get("source_url", ""),
                    "source_query": "directory_scrape",
                }

    # Merge: domain-based companies first, then name-only companies
    all_companies = list(companies_by_domain.values())
    # Add name-only companies that don't match any domain-based company name
    domain_names = {c["name"].lower() for c in all_companies}
    for comp in companies_by_name.values():
        if comp["name"].lower() not in domain_names:
            all_companies.append(comp)

    logger.info(f"ICP Discovery: found {len(all_companies)} unique companies from {len(queries)} queries")

    return {
        "companies": all_companies,
        "total_found": len(all_companies),
        "queries_run": len(queries),
    }
