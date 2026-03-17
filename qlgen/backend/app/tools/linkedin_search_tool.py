import re
import time

from strands import tool


@tool
def find_linkedin_profiles(
    company_name: str,
    titles: list[str] = None,
) -> dict:
    """
    Find LinkedIn profiles of decision-makers at a company using DuckDuckGo.
    FREE, no API key required. Uses site:linkedin.com/in searches.
    BEST FOR: Finding contacts when Apollo/Hunter are rate-limited.
    USE IN STAGES: Contact Discovery (Stage 2) or Contact Enrichment (Stage 3).

    Args:
        company_name: Name of the company to search contacts for
        titles: Job titles to search for (defaults to CEO, CTO, VP Engineering, Head of Product)

    Returns:
        dict with 'profiles' list, 'company', and 'titles_searched'
    """
    if not titles:
        titles = ["CEO", "CTO", "VP Engineering", "Head of Product"]

    try:
        from ddgs import DDGS
    except ImportError:
        return {"error": "ddgs package not installed", "profiles": []}

    profiles = []
    seen_urls = set()
    linkedin_pattern = re.compile(r"https?://(?:www\.)?linkedin\.com/in/([\w-]+)")

    for i, title in enumerate(titles):
        if i > 0:
            time.sleep(2)  # Rate limit between searches

        query = f'site:linkedin.com/in "{company_name}" "{title}"'
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
        except Exception:
            continue

        for r in results:
            href = r.get("href", "")
            match = linkedin_pattern.search(href)
            if not match:
                continue

            url = href.split("?")[0]  # Strip query params
            if url in seen_urls:
                continue
            seen_urls.add(url)

            profiles.append({
                "title_searched": title,
                "name": r.get("title", "").split(" - ")[0].split(" | ")[0].strip(),
                "linkedin_url": url,
                "linkedin_slug": match.group(1),
                "snippet": r.get("body", "")[:200],
            })

    return {
        "profiles": profiles,
        "company": company_name,
        "titles_searched": titles,
    }
