from datetime import datetime, timedelta

import httpx
from strands import tool
from app.config import get_settings

EVENTREGISTRY_URL = "https://newsapi.ai/api/v1/article/getArticles"

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: NewsAPI.ai limit reached. "
    "Do NOT retry. Use tavily_search or duckduckgo_search "
    "'[company] news' as alternatives."
)


@tool
def get_news_sentiment(
    company_name: str,
    days: int = 7,
) -> dict:
    """
    Fetch recent news articles about a company with sentiment scores.
    Uses NewsAPI.ai (EventRegistry) — requires NEWS_API_KEY.
    BEST FOR: Detecting recent press, announcements, funding news, or risk signals.
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

    # EventRegistry uses YYYY-MM-DD date format (no time component)
    date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    payload = {
        "apiKey": api_key,
        "keyword": company_name,
        "keywordSearchMode": "simple",
        "lang": "eng",
        "dateStart": date_from,
        "articlesCount": 10,
        "resultType": "articles",
        "articlesSortBy": "date",
        "articlesSortByAsc": False,
        "includeArticleSentiment": True,
        "includeArticleCategories": False,
        "includeArticleImage": False,
    }

    try:
        resp = httpx.post(EVENTREGISTRY_URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        raw_articles = data.get("articles", {}).get("results", [])

        articles = []
        for article in raw_articles:
            source = article.get("source", {})
            source_name = source.get("title", "") if isinstance(source, dict) else str(source)

            sentiment_raw = article.get("sentiment")
            if sentiment_raw is None:
                sentiment_label = "neutral"
                sentiment_score = None
            elif sentiment_raw > 0.1:
                sentiment_label = "positive"
                sentiment_score = round(sentiment_raw, 3)
            elif sentiment_raw < -0.1:
                sentiment_label = "negative"
                sentiment_score = round(abs(sentiment_raw), 3)
            else:
                sentiment_label = "neutral"
                sentiment_score = round(abs(sentiment_raw), 3)

            articles.append({
                "title": article.get("title", ""),
                "source": source_name,
                "published_date": article.get("dateTime", article.get("date", "")),
                "url": article.get("url", ""),
                "description": (article.get("body") or "")[:300],
                "sentiment": sentiment_label,
                "sentiment_score": sentiment_score,
            })

        return {
            "company": company_name,
            "days_searched": days,
            "articles": articles,
            "total_found": data.get("articles", {}).get("totalResults", len(articles)),
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "articles": []}
        return {"error": str(e), "articles": []}
    except Exception as e:
        return {"error": str(e), "articles": []}
