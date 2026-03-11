"""Comprehensive single-company research tool.

Takes a company name/domain and internally runs DuckDuckGo searches,
scrapes team/about pages, finds LinkedIn profiles, and gathers financial
data — all in a single tool call. Returns compiled contacts, financial
data, news, and tech signals.
"""

import re
import logging
import time
from urllib.parse import urlparse

import httpx
from strands import tool

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
LINKEDIN_PATTERN = re.compile(r"https?://(?:www\.)?linkedin\.com/in/([\w-]+)")

GENERIC_EMAIL_PREFIXES = {
    "support", "info", "hello", "contact", "sales", "noreply", "no-reply",
    "privacy", "legal", "press", "admin", "help", "billing", "team",
    "feedback", "careers", "jobs", "hr", "marketing", "media", "office",
    "enquiries", "inquiries", "general", "service", "webmaster", "postmaster",
}

TEAM_PATHS = ["/team", "/about", "/about-us", "/leadership", "/our-team", "/people"]


def _ddg_search(query: str, max_results: int = 8) -> list[dict]:
    """Run a DuckDuckGo search, return results. Handles rate limiting."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        if "ratelimit" in str(e).lower():
            logger.warning(f"DDG rate limited, waiting 30s: {e}")
            time.sleep(30)
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            except Exception:
                pass
        return []


def _scrape_page(url: str) -> dict:
    """Scrape a webpage, return title + text content + emails found."""
    try:
        from bs4 import BeautifulSoup
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 qlGen Research Bot"},
        )
        if response.status_code != 200:
            return {"content": "", "emails": [], "title": ""}

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)[:5000]
        title = soup.title.string if soup.title else ""

        # Extract emails
        emails = set()
        for email in EMAIL_REGEX.findall(text):
            prefix = email.split("@")[0].lower()
            if prefix not in GENERIC_EMAIL_PREFIXES:
                emails.add(email.lower())

        return {"content": text, "emails": sorted(emails), "title": title}
    except Exception:
        return {"content": "", "emails": [], "title": ""}


def _find_linkedin_profiles(company_name: str, titles: list[str]) -> list[dict]:
    """Search LinkedIn for people at a company using 2 broad queries (not one per title)."""
    profiles = []
    seen_urls = set()

    role_terms = " OR ".join(f'"{t}"' for t in titles[:6])

    # Single broad query covering all titles
    time.sleep(2)
    results = _ddg_search(
        f'site:linkedin.com/in "{company_name}" ({role_terms})',
        max_results=15,
    )
    for r in results:
        href = r.get("href", "")
        match = LINKEDIN_PATTERN.search(href)
        if not match:
            continue
        url = href.split("?")[0]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        name = r.get("title", "").split(" - ")[0].split(" | ")[0].strip()
        profiles.append({
            "name": name,
            "linkedin_url": url,
            "snippet": r.get("body", "")[:200],
        })

    return profiles


def _search_company_info(company_name: str, domain: str) -> dict:
    """Search for company financials, news, and general info."""
    info = {
        "revenue_signals": [],
        "funding_signals": [],
        "news": [],
        "tech_signals": [],
        "employee_signals": [],
    }

    # Search 1: General company info + revenue
    time.sleep(1)
    results = _ddg_search(f'"{company_name}" revenue employees funding', max_results=8)
    for r in results:
        body = r.get("body", "").lower()
        if any(kw in body for kw in ["revenue", "million", "billion", "$", "funding", "raised"]):
            info["revenue_signals"].append({
                "text": r["body"][:200],
                "url": r.get("href", ""),
                "title": r.get("title", ""),
            })
        if any(kw in body for kw in ["employees", "team", "workforce", "headcount"]):
            info["employee_signals"].append(r["body"][:150])

    # Search 2: Funding / investors
    time.sleep(1)
    results = _ddg_search(f'"{company_name}" site:crunchbase.com OR site:pitchbook.com OR "series" "funding"', max_results=5)
    for r in results:
        info["funding_signals"].append({
            "text": r.get("body", "")[:200],
            "url": r.get("href", ""),
            "title": r.get("title", ""),
        })

    # Search 3: Recent news
    time.sleep(1)
    results = _ddg_search(f'"{company_name}" news 2025 2026', max_results=5)
    for r in results:
        info["news"].append({
            "title": r.get("title", ""),
            "snippet": r.get("body", "")[:150],
            "url": r.get("href", ""),
        })

    # Search 4: Tech stack / job postings
    time.sleep(1)
    results = _ddg_search(f'"{company_name}" technology stack OR careers OR engineering', max_results=5)
    for r in results:
        body = r.get("body", "").lower()
        if any(kw in body for kw in ["technology", "stack", "platform", "engineering", "software", "cloud", "aws", "python", "java"]):
            info["tech_signals"].append(r.get("body", "")[:150])

    return info


@tool
def research_company(
    company_name: str,
    company_domain: str = "",
    target_roles: list[str] = None,
) -> dict:
    """
    Comprehensive research on a single company. Internally runs multiple
    DuckDuckGo searches, scrapes team/about pages, finds LinkedIn profiles,
    and gathers financial/news data — all in ONE tool call.

    Call this ONCE per company during Stage 2-4 to get contacts, financial data,
    news, and tech signals. It replaces the need for 5-10 individual tool calls
    per company.

    Args:
        company_name: Name of the company to research
        company_domain: Company's website domain (e.g. "acme.com"). If empty,
            will attempt to find it.
        target_roles: Decision-maker roles to search for (e.g. ["CEO", "CTO", "VP Engineering"]).
            Defaults to CEO, CTO, COO, VP Engineering, Head of Product, CDO.

    Returns:
        dict with:
        - 'company_info': basic company details found
        - 'contacts': list of people found with name, title, linkedin, email
        - 'financials': revenue/funding signals with source URLs
        - 'news': recent news items
        - 'tech_signals': technology indicators
        - 'team_emails': emails found on team pages
    """
    if not target_roles:
        target_roles = ["CEO", "CTO", "COO", "VP Engineering", "Head of Product", "CDO"]

    # Step 1: Find domain if not provided
    if not company_domain:
        results = _ddg_search(f'"{company_name}" official website', max_results=3)
        for r in results:
            href = r.get("href", "")
            try:
                parsed = urlparse(href)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                # Skip obvious non-company domains
                if domain and not any(
                    domain.endswith(s) for s in [
                        "wikipedia.org", "linkedin.com", "crunchbase.com",
                        "bloomberg.com", "google.com", "facebook.com",
                    ]
                ):
                    company_domain = domain
                    break
            except Exception:
                continue
        time.sleep(1)

    # Step 2: Scrape team/about pages for emails
    team_emails = []
    about_content = ""
    if company_domain:
        base = f"https://{company_domain}"
        for path in TEAM_PATHS[:4]:
            url = f"{base}{path}"
            time.sleep(0.5)
            page = _scrape_page(url)
            if page["emails"]:
                team_emails.extend(page["emails"])
            if page["content"] and not about_content:
                about_content = page["content"][:2000]

    # Step 3: Find LinkedIn profiles for decision-makers
    linkedin_profiles = _find_linkedin_profiles(company_name, target_roles)

    # Step 4: Merge contacts — combine LinkedIn profiles with emails
    contacts = []
    used_emails = set()
    for profile in linkedin_profiles:
        contact = {
            "full_name": profile.get("name", ""),
            "designation": profile.get("title_searched", ""),
            "linkedin_url": profile.get("linkedin_url", ""),
            "email": None,
            "source": "linkedin_search",
        }
        # Try to match email by name
        if team_emails and profile["name"]:
            name_parts = profile["name"].lower().split()
            for email in team_emails:
                if email in used_emails:
                    continue
                email_prefix = email.split("@")[0].lower()
                if any(part in email_prefix for part in name_parts if len(part) > 2):
                    contact["email"] = email
                    used_emails.add(email)
                    break
        contacts.append(contact)

    # Add remaining team emails as unmatched contacts
    for email in team_emails:
        if email not in used_emails:
            contacts.append({
                "full_name": None,
                "designation": None,
                "linkedin_url": None,
                "email": email,
                "source": "team_page",
            })

    # Step 5: Search for company info (financials, news, tech)
    company_info = _search_company_info(company_name, company_domain)

    # Step 6: Extract company description from about page
    description = ""
    if about_content:
        # Take first meaningful paragraph
        for line in about_content.split("\n"):
            line = line.strip()
            if len(line) > 50 and not any(kw in line.lower() for kw in ["cookie", "privacy", "terms"]):
                description = line[:300]
                break

    return {
        "company_name": company_name,
        "company_domain": company_domain,
        "description": description,
        "contacts": contacts[:10],  # Cap at 10 contacts
        "financials": {
            "revenue_signals": company_info["revenue_signals"][:5],
            "funding_signals": company_info["funding_signals"][:5],
            "employee_signals": company_info["employee_signals"][:3],
        },
        "news": company_info["news"][:5],
        "tech_signals": company_info["tech_signals"][:5],
        "team_emails": team_emails[:10],
        "linkedin_profiles_found": len(linkedin_profiles),
        "total_contacts_found": len(contacts),
    }
