from datetime import datetime, timedelta

import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: NewsAPI limit reached (100 calls/day on free tier). "
    "Do NOT retry. Use tavily_search or duckduckgo_search "
    "'[company] news' as alternatives."
)


@tool
def get_news_sentiment(
    company_name: str,
    days: int = 7,
) -> dict:
    """
    Fetch recent financial news and score sentiment for each article.
    Uses NewsAPI for headlines and FinBERT for sentiment scoring.
    Requires NEWS_API_KEY. Free tier: 100 calls/day.
    BEST FOR: Detecting reputational or financial risk signals,
    positive momentum, or negative press for a company.
    USE IN STAGE: BANT Scoring (Stage 4) — Timing and Need dimensions.

    Args:
        company_name: Company name to search news for (e.g. 'Stripe', 'Tesla')
        days: How many days back to search, default 7

    Returns:
        dict with articles list (title, source, date, url, sentiment)
    """
    settings = get_settings()
    api_key = settings.NEWS_API_KEY

    if not api_key:
        return {
            "error": "NEWS_API_KEY not configured. Use free alternatives: "
                     "tavily_search '[company] news' or "
                     "duckduckgo_search '[company] recent news'.",
            "articles": [],
        }

    from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        resp = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": company_name,
                "from": from_date,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 10,
                "apiKey": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            return {
                "error": data.get("message", "NewsAPI returned an error"),
                "articles": [],
            }

        raw_articles = data.get("articles", [])

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "articles": []}
        return {"error": str(e), "articles": []}
    except Exception as e:
        return {"error": str(e), "articles": []}

    # Try FinBERT sentiment scoring
    sentiments = _score_sentiments([a.get("title", "") for a in raw_articles])

    articles = []
    for i, article in enumerate(raw_articles):
        entry = {
            "title": article.get("title", ""),
            "source": article.get("source", {}).get("name", ""),
            "published_date": article.get("publishedAt", ""),
            "url": article.get("url", ""),
            "description": (article.get("description") or "")[:300],
        }
        if sentiments and i < len(sentiments):
            entry["sentiment"] = sentiments[i]["label"]
            entry["sentiment_confidence"] = sentiments[i]["score"]
        articles.append(entry)

    result = {
        "company": company_name,
        "days_searched": days,
        "articles": articles,
        "total_found": data.get("totalResults", len(articles)),
    }

    if not sentiments:
        result["sentiment_note"] = (
            "FinBERT not available (install transformers + torch). "
            "Articles returned without sentiment scores."
        )

    return result


def _score_sentiments(texts: list[str]) -> list[dict] | None:
    """Score sentiment using FinBERT. Returns None if libraries unavailable."""
    try:
        from transformers import pipeline
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
        )
        results = sentiment_pipeline(texts)
        return [{"label": r["label"], "score": round(r["score"], 3)} for r in results]
    except Exception:
        return None
