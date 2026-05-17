"""Resilient multi-source search with automatic fallback.

Provides a single `resilient_search()` function that signal detectors call
instead of importing duckduckgo_search directly. Fallback chain:

    DDG (free) → Exa (paid) → news_sentiment (paid)

All results are normalized to a common format: {title, body, href}.
Error/rate-limit dicts are filtered out before returning.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def resilient_search(
    query: str,
    max_results: int = 5,
    company_name: str | None = None,
) -> tuple[list[dict], str]:
    """Try multiple search backends with automatic fallback.

    Returns (articles, source_tool) where articles is a list of normalized
    dicts with keys: title, body, href. source_tool is the name of the
    backend that produced the results.
    """

    # 1. Try DuckDuckGo (free, no API key)
    try:
        from app.tools.duckduckgo_tool import duckduckgo_search

        raw = await asyncio.to_thread(
            duckduckgo_search, query=query, max_results=max_results,
        )
        articles = _filter_valid_articles(raw if isinstance(raw, list) else [])
        if articles:
            return articles, "duckduckgo_search"
        if _is_rate_limited(raw):
            logger.warning("DDG rate-limited, falling back to Exa")
    except Exception as e:
        logger.warning(f"DDG search failed: {e}")

    # 2. Try Exa (paid, requires EXA_API_KEY)
    try:
        from app.config import get_settings

        settings = get_settings()
        if settings.EXA_API_KEY:
            from app.tools.exa_tool import exa_search

            raw = await asyncio.to_thread(
                exa_search, query=query, num_results=max_results,
            )
            if isinstance(raw, dict) and not raw.get("rate_limited") and not raw.get("error"):
                articles = _normalize_exa(raw)
                if articles:
                    return articles, "exa_search"
            elif _is_rate_limited_dict(raw):
                logger.warning("Exa rate-limited, falling back to news_sentiment")
    except Exception as e:
        logger.warning(f"Exa search failed: {e}")

    # 3. Try news_sentiment (paid, requires NEWS_API_KEY, needs company_name)
    if company_name:
        try:
            from app.config import get_settings

            settings = get_settings()
            if settings.NEWS_API_KEY:
                from app.tools.news_sentiment_tool import get_news_sentiment

                raw = await asyncio.to_thread(
                    get_news_sentiment, company_name=company_name, days=14,
                )
                if isinstance(raw, dict) and not raw.get("rate_limited") and not raw.get("error"):
                    articles = _normalize_news(raw)
                    if articles:
                        return articles, "news_sentiment"
        except Exception as e:
            logger.warning(f"News sentiment search failed: {e}")

    logger.warning(f"All search backends failed for query: {query[:100]}")
    return [], "none"


# ──────────────────────────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────────────────────────

def _is_rate_limited(raw) -> bool:
    """Check if a tool response indicates rate limiting (list or dict)."""
    if isinstance(raw, list) and raw:
        first = raw[0]
        return isinstance(first, dict) and bool(
            first.get("rate_limited") or first.get("error")
        )
    if isinstance(raw, dict):
        return bool(raw.get("rate_limited") or raw.get("error"))
    return False


def _is_rate_limited_dict(raw: dict) -> bool:
    """Check if a dict response indicates rate limiting."""
    return bool(raw.get("rate_limited") or raw.get("error"))


def _filter_valid_articles(articles: list) -> list[dict]:
    """Remove error/rate-limit dicts and articles with no content."""
    return [
        a for a in articles
        if isinstance(a, dict)
        and not a.get("rate_limited")
        and not a.get("error")
        and (a.get("title") or a.get("body") or a.get("content") or a.get("text"))
    ]


# ──────────────────────────────────────────────────────────────────
# Normalization: convert tool-specific formats to {title, body, href}
# ──────────────────────────────────────────────────────────────────

def _normalize_exa(raw: dict) -> list[dict]:
    """Normalize Exa results to DDG-compatible format."""
    results = raw.get("results", [])
    normalized = []
    for r in results:
        title = r.get("title") or ""
        text = r.get("text") or ""
        url = r.get("url") or ""
        if title or text:
            normalized.append({
                "title": title,
                "body": text,
                "href": url,
            })
    return normalized


def _normalize_news(raw: dict) -> list[dict]:
    """Normalize news_sentiment results to DDG-compatible format."""
    articles = raw.get("articles", [])
    normalized = []
    for a in articles:
        title = a.get("title") or ""
        description = a.get("description") or ""
        url = a.get("url") or ""
        if title or description:
            normalized.append({
                "title": title,
                "body": description,
                "href": url,
                "published_date": a.get("published_date"),
            })
    return normalized
