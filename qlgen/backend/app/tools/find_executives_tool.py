"""Aggressive multi-method executive/contact finder tool.

Uses 8 different discovery methods to find decision-makers at a company,
far more thorough than a simple LinkedIn search. All methods use free
public sources — no API keys required.
"""

import re
import logging
import time
from urllib.parse import urlparse, quote_plus

import httpx
from strands import tool

logger = logging.getLogger(__name__)

LINKEDIN_PATTERN = re.compile(r"https?://(?:www\.)?linkedin\.com/in/([\w-]+)")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

GENERIC_EMAIL_PREFIXES = {
    "support", "info", "hello", "contact", "sales", "noreply", "no-reply",
    "privacy", "legal", "press", "admin", "help", "billing", "team",
    "feedback", "careers", "jobs", "hr", "marketing", "media", "office",
    "enquiries", "inquiries", "general", "service", "webmaster", "postmaster",
    "notifications", "alerts", "abuse", "security", "news", "newsletter",
}

LEADERSHIP_PATHS = [
    "/team", "/about", "/about-us", "/leadership", "/our-team", "/people",
    "/management", "/executives", "/founders", "/board", "/company/team",
    "/company/about", "/about/team", "/about/leadership",
]

DEFAULT_ROLES = ["CEO", "CTO", "COO", "CIO", "CDO", "VP Engineering",
                 "Head of Engineering", "Founder", "Co-Founder", "President",
                 "Chief Medical Officer", "VP Product", "VP R&D"]


def _ddg(query: str, max_results: int = 8) -> list[dict]:
    """DuckDuckGo search with rate-limit backoff."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        if "ratelimit" in str(e).lower():
            logger.warning("DDG rate limit hit, waiting 30s")
            time.sleep(30)
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            except Exception:
                pass
        return []


def _fetch(url: str, timeout: int = 12) -> str:
    """Fetch a URL and return text content."""
    try:
        from bs4 import BeautifulSoup
        resp = httpx.get(
            url, follow_redirects=True, timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 qlGen Research Bot"},
        )
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:8000]
    except Exception:
        return ""


def _extract_emails(text: str, domain: str) -> list[str]:
    """Extract personal (non-generic) emails, prioritising company domain."""
    found = set()
    for email in EMAIL_REGEX.findall(text):
        prefix = email.split("@")[0].lower()
        if prefix not in GENERIC_EMAIL_PREFIXES:
            found.add(email.lower())
    # Prioritise emails matching company domain
    company_emails = [e for e in found if domain and domain in e]
    other_emails = [e for e in found if not domain or domain not in e]
    return company_emails + other_emails


def _parse_linkedin_from_results(results: list[dict]) -> list[dict]:
    """Extract LinkedIn profiles from DDG results."""
    profiles = []
    seen = set()
    for r in results:
        href = r.get("href", "")
        match = LINKEDIN_PATTERN.search(href)
        if not match:
            continue
        url = href.split("?")[0]
        if url in seen:
            continue
        seen.add(url)
        name = r.get("title", "").split(" - ")[0].split(" | ")[0].strip()
        profiles.append({
            "name": name,
            "linkedin_url": url,
            "slug": match.group(1),
            "snippet": r.get("body", "")[:200],
            "source": "linkedin_search",
        })
    return profiles


# ── Method 1 & 2: LinkedIn searches (2 broad queries instead of N per-title) ──

def _method_linkedin_searches(company_name: str, roles: list[str]) -> list[dict]:
    """Two broad LinkedIn searches covering all target roles at once.

    Uses OR syntax to get multiple profiles in a single query, dramatically
    reducing DuckDuckGo request count vs. one query per role.
    """
    profiles = []
    seen_urls = set()

    # Build role groups for 2 searches
    role_terms = " OR ".join(f'"{r}"' for r in roles[:6])

    # Query 1: Title-focused
    time.sleep(2)
    results = _ddg(
        f'site:linkedin.com/in "{company_name}" ({role_terms})',
        max_results=15,
    )
    for p in _parse_linkedin_from_results(results):
        if p["linkedin_url"] not in seen_urls:
            seen_urls.add(p["linkedin_url"])
            p["method"] = "linkedin_title_broad"
            profiles.append(p)

    # Query 2: Founder/executive catch-all
    time.sleep(2)
    results = _ddg(
        f'site:linkedin.com/in "{company_name}" (founder OR executive OR president)',
        max_results=10,
    )
    for p in _parse_linkedin_from_results(results):
        if p["linkedin_url"] not in seen_urls:
            seen_urls.add(p["linkedin_url"])
            p["method"] = "linkedin_broad"
            profiles.append(p)

    return profiles


# ── Method 3: Crunchbase/PitchBook people pages ───────────────────────────────

def _method_crunchbase(company_name: str) -> list[dict]:
    """Search Crunchbase and PitchBook for company people listings."""
    contacts = []
    queries = [
        f'site:crunchbase.com "{company_name}" people team founders',
        f'site:pitchbook.com "{company_name}" executives leadership',
    ]
    for query in queries:
        time.sleep(2)
        results = _ddg(query, max_results=5)
        for r in results:
            href = r.get("href", "")
            body = r.get("body", "")
            # Scrape the actual crunchbase/pitchbook page for names
            if any(d in href for d in ["crunchbase.com", "pitchbook.com"]):
                time.sleep(1)
                content = _fetch(href)
                if content:
                    # Extract names adjacent to title keywords
                    for line in content.split("\n"):
                        line = line.strip()
                        if (2 < len(line) < 60 and
                                any(kw in line.lower() for kw in
                                    ["ceo", "cto", "coo", "founder", "president",
                                     "chief", "vice president", "vp ", "director"])):
                            contacts.append({
                                "name": line,
                                "snippet": body[:150],
                                "source_url": href,
                                "method": "crunchbase_pitchbook",
                            })
    return contacts[:10]


# ── Method 4: Company website leadership pages ───────────────────────────────

def _method_website_leadership(company_name: str, domain: str) -> list[dict]:
    """Scrape the company's own team/leadership/about pages."""
    if not domain:
        return []

    contacts = []
    base = f"https://{domain}"
    for path in LEADERSHIP_PATHS[:8]:
        url = f"{base}{path}"
        time.sleep(0.8)
        content = _fetch(url)
        if not content:
            continue

        emails = _extract_emails(content, domain)
        linkedin_urls = set()
        for match in LINKEDIN_PATTERN.finditer(content):
            linkedin_urls.add(f"https://linkedin.com/in/{match.group(1)}")

        # Extract names near title keywords from page content
        lines = content.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for lines with exec titles
            if any(kw in line.lower() for kw in
                   ["ceo", "cto", "coo", "chief", "founder", "president",
                    "vice president", "director", "head of"]):
                # Adjacent lines might be the name
                for offset in [-1, 1, -2]:
                    idx = i + offset
                    if 0 <= idx < len(lines):
                        candidate = lines[idx].strip()
                        if (3 < len(candidate) < 50 and
                                candidate[0].isupper() and
                                not candidate.startswith("http") and
                                not any(kw in candidate.lower() for kw in
                                        ["click", "read", "learn", "more", "view",
                                         "contact", "email", "phone"])):
                            contacts.append({
                                "name": candidate,
                                "designation_hint": line,
                                "source_url": url,
                                "method": "website_leadership",
                            })
                            break

        # If we found emails or linkedin, record them
        for email in emails[:5]:
            contacts.append({
                "email": email,
                "source_url": url,
                "method": "website_email",
            })
        for li_url in list(linkedin_urls)[:5]:
            contacts.append({
                "linkedin_url": li_url,
                "source_url": url,
                "method": "website_linkedin_link",
            })

        if contacts:
            break  # Got data from this page, stop scanning more paths

    return contacts[:15]


# ── Method 5: Press releases / news mentions ─────────────────────────────────

def _method_press_releases(company_name: str) -> list[dict]:
    """Find executive names in press releases and news articles."""
    from datetime import datetime
    current_year = datetime.now().year
    last_year = current_year - 1
    contacts = []
    queries = [
        f'"{company_name}" CEO interview {last_year} {current_year}',
        f'"{company_name}" press release contact named',
        f'"{company_name}" founder announcement',
    ]
    for query in queries:
        time.sleep(2)
        results = _ddg(query, max_results=5)
        for r in results:
            body = r.get("body", "")
            href = r.get("href", "")
            # Look for name patterns: "John Smith, CEO of [company]"
            name_title_pattern = re.findall(
                r"([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"
                r"[,\s]+(?:CEO|CTO|COO|CIO|founder|president|Chief|Vice President|VP)",
                body,
            )
            for name in name_title_pattern[:3]:
                if len(name.split()) >= 2:
                    # Extract title
                    title_match = re.search(
                        r"" + re.escape(name) + r"[,\s]+([^,\.]+(?:CEO|CTO|COO|CIO|founder|president|Chief|VP)[^,\.]*)",
                        body,
                    )
                    contacts.append({
                        "name": name.strip(),
                        "designation_hint": title_match.group(1).strip()[:80] if title_match else None,
                        "source_url": href,
                        "snippet": body[:150],
                        "method": "press_release",
                    })
    return contacts[:10]


# ── Method 6: Email pattern inference ────────────────────────────────────────

def _method_email_inference(known_contacts: list[dict], domain: str) -> list[dict]:
    """Infer email addresses for contacts that have names but no email.

    Tries common patterns: first@domain, first.last@domain, f.last@domain.
    """
    if not domain:
        return []

    enriched = []
    for c in known_contacts:
        name = c.get("name") or c.get("full_name", "")
        if not name or c.get("email"):
            enriched.append(c)
            continue

        parts = name.lower().split()
        if len(parts) < 2:
            enriched.append(c)
            continue

        first, last = parts[0], parts[-1]
        # Common patterns
        candidates = [
            f"{first}@{domain}",
            f"{first}.{last}@{domain}",
            f"{first[0]}{last}@{domain}",
            f"{first[0]}.{last}@{domain}",
            f"{first}{last[0]}@{domain}",
        ]
        # Mark all as inferred (confidence 0.4), let the agent decide
        c_copy = dict(c)
        c_copy["inferred_emails"] = candidates[:3]
        c_copy["email_confidence"] = 0.4
        enriched.append(c_copy)

    return enriched


# ── Method 7: Conference / event speakers ─────────────────────────────────────

def _method_conference_speakers(company_name: str, industry: str = "") -> list[dict]:
    """Find executives who have spoken at industry conferences."""
    from datetime import datetime
    current_year = datetime.now().year
    last_year = current_year - 1
    contacts = []
    industry_term = industry or "medtech medical device"
    results = _ddg(
        f'"{company_name}" "{industry_term}" conference speaker presentation {last_year} {current_year}',
        max_results=5,
    )
    for r in results:
        body = r.get("body", "")
        href = r.get("href", "")
        name_pattern = re.findall(
            r"([A-Z][a-z]+ [A-Z][a-z]+).*?(?:" + re.escape(company_name) + r")",
            body,
        )
        for name in name_pattern[:3]:
            contacts.append({
                "name": name.strip(),
                "source_url": href,
                "snippet": body[:150],
                "method": "conference_speaker",
            })
    return contacts[:5]


# ── Merge + Deduplicate ────────────────────────────────────────────────────────

def _merge_contacts(all_raw: list[dict]) -> list[dict]:
    """Merge and deduplicate contacts from all methods.

    Groups by LinkedIn URL or name (case-insensitive), merging fields.
    """
    by_linkedin: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    no_key: list[dict] = []

    def _merge(existing: dict, new: dict) -> dict:
        for k, v in new.items():
            if v and not existing.get(k):
                existing[k] = v
        # Merge methods list
        existing.setdefault("methods", set())
        if isinstance(existing["methods"], set):
            existing["methods"].add(new.get("method", ""))
        return existing

    for raw in all_raw:
        li = raw.get("linkedin_url", "")
        name = (raw.get("name") or raw.get("full_name") or "").strip().lower()

        if li:
            slug = li.rstrip("/").split("/")[-1].lower()
            if slug in by_linkedin:
                by_linkedin[slug] = _merge(by_linkedin[slug], raw)
            else:
                by_linkedin[slug] = dict(raw)
                by_linkedin[slug]["methods"] = {raw.get("method", "")}
        elif name and len(name) > 3:
            if name in by_name:
                by_name[name] = _merge(by_name[name], raw)
            else:
                by_name[name] = dict(raw)
                by_name[name]["methods"] = {raw.get("method", "")}
        else:
            no_key.append(raw)

    merged = list(by_linkedin.values()) + list(by_name.values()) + no_key

    # Convert methods set to list for JSON serialisation
    for c in merged:
        if isinstance(c.get("methods"), set):
            c["methods"] = sorted(c["methods"] - {""})

    return merged


@tool
def find_company_executives(
    company_name: str,
    company_domain: str = "",
    target_roles: list[str] = None,
    industry_hint: str = "",
) -> dict:
    """
    Aggressive multi-method executive and decision-maker finder.
    Uses 7 independent discovery methods to maximise contact coverage:

    1. LinkedIn title searches (site:linkedin.com/in searches per role)
    2. LinkedIn broad company search (CEO/CTO/founder terms)
    3. Crunchbase & PitchBook people pages
    4. Company website team/leadership page scraping
    5. Press releases and news article executive mentions
    6. Email pattern inference for named contacts
    7. Industry conference speaker lists

    Call this for EVERY company in Stage 2 to get comprehensive contacts.
    It internally handles rate limiting and merges results across methods.

    Args:
        company_name: Company name (e.g. "Polares Medical")
        company_domain: Company domain (e.g. "polaresmedical.com"). Leave empty
            to attempt auto-discovery.
        target_roles: Roles to search for. Defaults to CEO, CTO, COO, Founder,
            VP Engineering, Head of Engineering, CDO, President.
        industry_hint: Industry term for conference search (e.g. "medical device")

    Returns:
        dict with:
        - 'contacts': deduplicated list of executives found
        - 'total_found': total contact count
        - 'methods_used': which discovery methods returned data
        - 'emails_found': total emails collected
    """
    if not target_roles:
        target_roles = DEFAULT_ROLES

    # Resolve domain if not provided
    if not company_domain:
        results = _ddg(f'"{company_name}" official website -linkedin -crunchbase', max_results=3)
        for r in results:
            try:
                parsed = urlparse(r.get("href", ""))
                domain = parsed.netloc.lower().lstrip("www.")
                skip = {"linkedin.com", "crunchbase.com", "bloomberg.com",
                        "wikipedia.org", "google.com", "facebook.com", "glassdoor.com"}
                if domain and not any(domain.endswith(s) for s in skip):
                    company_domain = domain
                    break
            except Exception:
                pass
        time.sleep(1)

    all_raw: list[dict] = []
    methods_used: list[str] = []

    # Methods 1+2: LinkedIn (2 broad queries covering all roles, not one per role)
    li = _method_linkedin_searches(company_name, target_roles)
    if li:
        all_raw.extend(li)
        methods_used.append("linkedin")

    time.sleep(2)

    # Method 3: Crunchbase / PitchBook
    cb = _method_crunchbase(company_name)
    if cb:
        all_raw.extend(cb)
        methods_used.append("crunchbase_pitchbook")

    time.sleep(1)

    # Method 4: Company website leadership pages
    web = _method_website_leadership(company_name, company_domain)
    if web:
        all_raw.extend(web)
        methods_used.append("website_scrape")

    time.sleep(2)

    # Method 5: Press releases
    press = _method_press_releases(company_name)
    if press:
        all_raw.extend(press)
        methods_used.append("press_releases")

    time.sleep(2)

    # Method 7: Conference speakers
    conf = _method_conference_speakers(company_name, industry_hint)
    if conf:
        all_raw.extend(conf)
        methods_used.append("conferences")

    # Merge and deduplicate
    merged = _merge_contacts(all_raw)

    # Method 6: Email inference for contacts with names but no email
    merged = _method_email_inference(merged, company_domain)

    # Collect all emails found
    all_emails = []
    for c in merged:
        if c.get("email"):
            all_emails.append(c["email"])
        all_emails.extend(c.get("inferred_emails", []))

    logger.info(
        f"find_company_executives({company_name}): "
        f"{len(merged)} contacts via methods: {methods_used}"
    )

    return {
        "company_name": company_name,
        "company_domain": company_domain,
        "contacts": merged[:20],
        "total_found": len(merged),
        "methods_used": methods_used,
        "emails_found": len(set(all_emails)),
    }
