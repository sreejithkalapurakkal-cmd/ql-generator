import re

import httpx
from strands import tool

# Generic email prefixes to filter out (not personal contacts)
GENERIC_PREFIXES = {
    "support", "info", "hello", "contact", "sales", "noreply", "no-reply",
    "privacy", "legal", "press", "admin", "help", "billing", "team",
    "feedback", "careers", "jobs", "hr", "marketing", "media", "office",
    "enquiries", "inquiries", "general", "service", "webmaster", "postmaster",
    "abuse", "security", "compliance", "notifications", "alerts",
}

TEAM_PATHS = [
    "/team", "/about", "/people", "/company", "/our-team",
    "/about-us", "/leadership", "/about/team",
]

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)


@tool
def scrape_team_page(company_website: str) -> dict:
    """
    Scrape a company's team/about pages to find personal email addresses.
    FREE, no API key required. Tries multiple common team page paths.
    BEST FOR: Finding email addresses when Hunter/Apollo are rate-limited.
    USE IN STAGES: Contact Discovery (Stage 2) or Contact Enrichment (Stage 3).

    Args:
        company_website: Company's base domain or URL (e.g. "acme.com" or "https://acme.com")

    Returns:
        dict with 'emails' list, 'source_url', 'email_source', and 'pages_tried'
    """
    from bs4 import BeautifulSoup

    # Normalize the base URL
    base = company_website.strip().rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"

    headers = {"User-Agent": "Mozilla/5.0 qlGen Research Bot"}
    found_emails = set()
    source_url = None
    pages_tried = []

    for path in TEAM_PATHS:
        url = f"{base}{path}"
        pages_tried.append(url)
        try:
            response = httpx.get(
                url,
                follow_redirects=True,
                timeout=15,
                headers=headers,
            )
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove scripts/styles
            for tag in soup(["script", "style"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)
            emails = EMAIL_REGEX.findall(text)

            for email in emails:
                prefix = email.split("@")[0].lower()
                if prefix not in GENERIC_PREFIXES:
                    found_emails.add(email.lower())
                    if source_url is None:
                        source_url = url

        except Exception:
            continue

    return {
        "emails": sorted(found_emails),
        "source_url": source_url,
        "email_source": "team_page",
        "pages_tried": pages_tried,
    }
