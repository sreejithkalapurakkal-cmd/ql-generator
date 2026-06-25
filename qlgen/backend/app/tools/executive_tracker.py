"""Executive movement tracking tool.

Monitors executive leadership changes (new hires, departures, role changes)
at target companies using multiple data sources.
"""
import logging
import re

from strands import tool

logger = logging.getLogger(__name__)

# Executive title patterns for detection
C_SUITE_TITLES = [
    "ceo", "cfo", "cto", "coo", "cio", "cmo", "cdo", "cpo", "cro",
    "chief executive", "chief financial", "chief technology", "chief operating",
    "chief information", "chief marketing", "chief data", "chief product",
    "chief revenue", "chief people", "chief strategy", "chief legal",
]

VP_PLUS_TITLES = [
    "vice president", "vp ", "svp ", "evp ", "senior vice president",
    "executive vice president", "general manager", "managing director",
    "president", "head of", "director of",
]

BOARD_TITLES = [
    "board of directors", "board member", "board appointment",
    "independent director", "chairman", "chairwoman", "chairperson",
]

# Keywords indicating the type of change
CHANGE_KEYWORDS = {
    "new_hire": [
        "hired", "appointed", "named", "joins", "joined", "welcomed",
        "brought on", "tapped", "selected as", "new hire", "recruiting",
        "onboarded",
    ],
    "departure": [
        "departed", "leaving", "left", "resigned", "stepped down",
        "exits", "exited", "former", "departure", "parted ways",
        "transition out",
    ],
    "promotion": [
        "promoted", "elevated", "advanced to", "moved to", "named to",
        "expanded role", "new role", "takes over", "assumes role",
    ],
    "board_appointment": [
        "board of directors", "board appointment", "elected to board",
        "joined the board", "board seat", "independent director",
    ],
}


@tool
def track_executive_changes(
    company_name: str,
    domain: str,
    time_window_days: int = 90,
) -> dict:
    """Track executive leadership changes at a target company.

    Detects C-suite hires, departures, promotions, and board appointments
    by searching news and press sources.

    Args:
        company_name: Name of the company to monitor
        domain: Company domain (e.g., 'acme.com')
        time_window_days: How far back to look in days (default 90)

    Returns:
        dict with company, changes, signal_strength, total_changes
    """
    from app.tools.duckduckgo_tool import duckduckgo_search

    result = {
        "company": company_name,
        "changes": [],
        "signal_strength": 0.0,
        "total_changes": 0,
    }

    # Run multiple searches to capture different types of executive changes
    queries = [
        f'"{company_name}" executive appointment OR hire OR departure OR CEO OR CTO OR CDO',
        f'"{company_name}" new VP OR director OR chief officer',
    ]

    all_articles = []
    for query in queries:
        try:
            raw = duckduckgo_search(query=query, max_results=10)
            if isinstance(raw, list):
                articles = [
                    a for a in raw
                    if isinstance(a, dict)
                    and not a.get("rate_limited")
                    and not a.get("error")
                    and (a.get("title") or a.get("body"))
                ]
                all_articles.extend(articles)
        except Exception as e:
            logger.warning(
                f"Executive tracker search failed for '{company_name}' "
                f"with query '{query[:60]}': {e}"
            )

    if not all_articles:
        return result

    seen_names: set[str] = set()

    for article in all_articles:
        title = article.get("title", "") or ""
        body = article.get("body", "") or article.get("content", "") or ""
        href = article.get("href") or article.get("url")
        text = f"{title} {body}"
        text_lower = text.lower()

        # Verify the article is about this company
        company_lower = company_name.lower()
        domain_base = domain.split(".")[0].lower() if domain else ""
        if company_lower not in text_lower and domain_base not in text_lower:
            continue

        # Detect if this mentions an executive-level person
        has_c_suite = any(t in text_lower for t in C_SUITE_TITLES)
        has_vp_plus = any(t in text_lower for t in VP_PLUS_TITLES)
        has_board = any(t in text_lower for t in BOARD_TITLES)

        if not (has_c_suite or has_vp_plus or has_board):
            continue

        # Determine change type
        change_type = _detect_change_type(text_lower)
        if not change_type:
            # Default to new_hire if we can't determine the type
            change_type = "new_hire"

        # Extract the executive title mentioned
        detected_title = _extract_title(text_lower)

        # Try to extract a person's name from the text
        person_name = _extract_person_name(text, company_name)

        # Skip duplicates based on person name
        dedup_key = (person_name or title[:50]).lower()
        if dedup_key in seen_names:
            continue
        seen_names.add(dedup_key)

        # Try to extract a date reference
        date_ref = _extract_date_reference(text)

        change_record = {
            "name": person_name or "Unknown",
            "change_type": change_type,
            "title": detected_title or "Executive",
            "previous_title": None,
            "previous_company": None,
            "date": date_ref,
            "source_url": href,
        }

        # For new hires, try to detect previous company
        if change_type == "new_hire":
            prev = _extract_previous_company(text, company_name)
            if prev:
                change_record["previous_company"] = prev

        # For promotions, try to detect previous title
        if change_type == "promotion":
            prev_title = _extract_previous_title(text_lower, detected_title)
            if prev_title:
                change_record["previous_title"] = prev_title

        result["changes"].append(change_record)

    result["total_changes"] = len(result["changes"])

    # Calculate signal strength based on seniority and volume
    result["signal_strength"] = _calculate_signal_strength(result["changes"])

    return result


def _detect_change_type(text_lower: str) -> str | None:
    """Determine the type of executive change from text."""
    # Check board first (most specific)
    if any(kw in text_lower for kw in CHANGE_KEYWORDS["board_appointment"]):
        return "board_appointment"

    scores = {}
    for change_type, keywords in CHANGE_KEYWORDS.items():
        if change_type == "board_appointment":
            continue
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[change_type] = count

    if scores:
        return max(scores, key=scores.get)
    return None


def _extract_title(text_lower: str) -> str | None:
    """Extract the executive title from text."""
    # Check C-suite first
    for title in C_SUITE_TITLES:
        if title in text_lower:
            # Map abbreviations to full titles
            title_map = {
                "ceo": "Chief Executive Officer",
                "cfo": "Chief Financial Officer",
                "cto": "Chief Technology Officer",
                "coo": "Chief Operating Officer",
                "cio": "Chief Information Officer",
                "cmo": "Chief Marketing Officer",
                "cdo": "Chief Data Officer",
                "cpo": "Chief Product Officer",
                "cro": "Chief Revenue Officer",
            }
            if title in title_map:
                return title_map[title]
            return title.title()

    # Check VP+ titles
    vp_patterns = [
        r"((?:senior |executive )?vice president\s+(?:of\s+)?\w+(?:\s+\w+)?)",
        r"((?:svp|evp|vp)\s+(?:of\s+)?\w+(?:\s+\w+)?)",
        r"(head of\s+\w+(?:\s+\w+)?)",
        r"(director of\s+\w+(?:\s+\w+)?)",
        r"(general manager\b)",
        r"(managing director\b)",
    ]
    for pattern in vp_patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip().title()

    return None


def _extract_person_name(text: str, company_name: str) -> str | None:
    """Attempt to extract a person's name from the article text.

    Uses a simple heuristic: look for capitalized two-or-three-word sequences
    near executive title keywords.
    """
    # Pattern: two or three capitalized words that could be a name
    name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    candidates = re.findall(name_pattern, text)

    # Filter out the company name and common false positives
    skip_words = {
        company_name.lower(), "the company", "new york", "san francisco",
        "los angeles", "wall street", "silicon valley", "united states",
        "chief executive", "vice president", "board directors",
    }

    for candidate in candidates:
        if candidate.lower() not in skip_words and len(candidate.split()) >= 2:
            # Check it's not just common words
            words = candidate.split()
            if not all(w.lower() in {"the", "a", "an", "and", "or", "of", "in", "to", "for"} for w in words):
                return candidate

    return None


def _extract_date_reference(text: str) -> str | None:
    """Extract a date reference from the text."""
    # Look for common date patterns
    patterns = [
        r"(\w+\s+\d{1,2},?\s+\d{4})",        # January 15, 2026
        r"(\d{1,2}/\d{1,2}/\d{4})",            # 01/15/2026
        r"(\d{4}-\d{2}-\d{2})",                # 2026-01-15
        r"(Q[1-4]\s+\d{4})",                   # Q1 2026
        r"(\w+\s+\d{4})",                       # January 2026
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _extract_previous_company(text: str, current_company: str) -> str | None:
    """Try to extract the previous company for a new hire."""
    patterns = [
        r"(?:formerly|previously|from|ex-|left|joining from)\s+([A-Z][A-Za-z&\s]+?)(?:\s*[,.]|\s+(?:to|as|where))",
        r"(?:came from|was at|worked at|served at)\s+([A-Z][A-Za-z&\s]+?)(?:\s*[,.]|\s+(?:as|where|before))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            prev = match.group(1).strip()
            if prev.lower() != current_company.lower() and len(prev) > 2:
                return prev
    return None


def _extract_previous_title(text_lower: str, current_title: str | None) -> str | None:
    """Try to extract previous title for a promotion."""
    patterns = [
        r"(?:from|previously|formerly)\s+([\w\s]+?)\s+(?:to|as)\s+",
        r"(?:was|served as)\s+([\w\s]+?)\s+(?:before|prior to)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            prev_title = match.group(1).strip()
            if current_title and prev_title.lower() != current_title.lower():
                return prev_title.title()
    return None


def _calculate_signal_strength(changes: list[dict]) -> float:
    """Calculate signal strength (0-100) based on the executive changes detected."""
    if not changes:
        return 0.0

    score = 0.0

    for change in changes:
        title_lower = (change.get("title") or "").lower()
        change_type = change.get("change_type", "")

        # C-suite changes are highest weight
        if any(t in title_lower for t in ["chief", "ceo", "cfo", "cto", "coo", "cio", "cmo"]):
            score += 25.0
        # VP-level changes
        elif any(t in title_lower for t in ["vice president", "vp", "svp", "evp"]):
            score += 15.0
        # Director-level
        elif "director" in title_lower or "head of" in title_lower:
            score += 10.0
        else:
            score += 5.0

        # Departures and new hires are slightly stronger signals than promotions
        if change_type in ("new_hire", "departure"):
            score += 5.0
        elif change_type == "board_appointment":
            score += 10.0

    # Cap at 100
    return min(100.0, round(score, 1))
