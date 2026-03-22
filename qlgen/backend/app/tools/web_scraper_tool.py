import json
import re

import httpx
from strands import tool

from app.tools.retry_utils import httpx_get_with_retry

# Domains that block scraping (403) and waste tool calls.
# The agent should use exa_search or tavily_search for these instead.
_BLOCKED_DOMAINS = {
    "crunchbase.com",
    "pitchbook.com",
    "linkedin.com",
    "glassdoor.com",
    "zoominfo.com",
}

_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_GENERIC_EMAIL_PREFIXES = {
    "support", "info", "hello", "contact", "sales", "noreply", "no-reply",
    "privacy", "legal", "press", "admin", "help", "billing", "team",
    "feedback", "careers", "jobs", "hr", "marketing", "media", "office",
}


@tool
def scrape_webpage(url: str) -> dict:
    """
    Scrape a webpage to extract text content, metadata, structured data, and emails.
    BEST FOR: Reading company about pages, team pages, technology pages,
    and blog posts to extract detailed information not available via APIs.
    USE IN STAGES: Any stage - especially Contact Discovery (team pages)
    and BANT Scoring (gathering evidence).

    Args:
        url: The URL to scrape

    Returns:
        dict with 'url', 'title', 'content' (extracted text up to 10,000 chars),
        'meta' (page metadata), 'structured_data' (JSON-LD if present),
        'emails' (personal emails found on page), 'links', 'tech_signals' (detected technologies)
    """
    # Block known paywalled/anti-scraping sites to save tool budget
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        for blocked in _BLOCKED_DOMAINS:
            if blocked in domain:
                return {
                    "error": f"BLOCKED: {blocked} blocks scraping (always returns 403). "
                    "Do NOT retry. Use exa_search or tavily_search to find this information instead.",
                    "url": url,
                    "content": "",
                }
    except Exception:
        pass

    try:
        from bs4 import BeautifulSoup

        response = httpx_get_with_retry(
            url,
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 qlGen Research Bot"},
        )
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract metadata before decomposing tags
        meta = {}
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "") or tag.get("name", "")
            content = tag.get("content", "")
            if prop and content:
                if prop in ("og:title", "og:description", "og:type", "og:site_name",
                            "description", "author", "keywords"):
                    meta[prop] = content[:300]

        # Extract JSON-LD structured data
        structured_data = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    structured_data.append(data)
                elif isinstance(data, list):
                    structured_data.extend(data[:3])
            except (json.JSONDecodeError, TypeError):
                pass
        # Limit structured data size
        structured_data = structured_data[:3]

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_content = soup.get_text(separator="\n", strip=True)[:5000]

        # Extract personal emails from page text
        emails = set()
        for email in _EMAIL_REGEX.findall(text_content):
            prefix = email.split("@")[0].lower()
            if prefix not in _GENERIC_EMAIL_PREFIXES:
                emails.add(email.lower())

        # Detect client-side tech stack from raw HTML
        raw_html = response.text.lower()
        tech_signals = []
        _TECH_PATTERNS = {
            "React": ["react", "reactdom", "__next"],
            "Angular": ["ng-app", "ng-controller", "angular"],
            "Vue.js": ["vue.js", "vuex", "__vue__"],
            "Next.js": ["__next", "_next/static"],
            "Nuxt": ["__nuxt", "_nuxt/"],
            "Svelte": ["svelte"],
            "jQuery": ["jquery"],
            "Google Analytics": ["google-analytics.com", "gtag", "googletagmanager"],
            "Segment": ["segment.com/analytics", "analytics.js"],
            "Mixpanel": ["mixpanel"],
            "HubSpot": ["hubspot", "hs-scripts.com"],
            "Salesforce": ["salesforce", "pardot"],
            "Intercom": ["intercom", "widget.intercom.io"],
            "Zendesk": ["zendesk"],
            "Stripe": ["stripe.com/v3", "js.stripe.com"],
            "Cloudflare": ["cloudflare", "cdnjs.cloudflare.com"],
            "AWS": ["amazonaws.com"],
            "Google Cloud": ["googleapis.com", "storage.googleapis.com"],
            "Shopify": ["shopify", "cdn.shopify.com"],
            "WordPress": ["wp-content", "wp-includes"],
            "Webflow": ["webflow"],
        }
        for tech, patterns in _TECH_PATTERNS.items():
            if any(p in raw_html for p in patterns):
                tech_signals.append(tech)

        return {
            "url": url,
            "title": soup.title.string if soup.title else "",
            "content": text_content,
            "meta": meta,
            "structured_data": structured_data,
            "emails": sorted(emails)[:20],
            "links": [a.get("href") for a in soup.find_all("a", href=True)[:50]],
            "tech_signals": tech_signals,
        }
    except Exception as e:
        return {"url": url, "error": str(e), "content": "", "meta": {},
                "structured_data": [], "emails": [], "links": [],
                "tech_signals": []}
