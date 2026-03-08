import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Financial Modeling Prep API limit reached. Do NOT retry. "
    "Use get_market_data (Yahoo Finance) or duckduckgo_search "
    "'[company] institutional holders analyst rating' as alternatives."
)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


@tool
def get_investor_data(ticker: str) -> dict:
    """
    Get institutional holders, insider trades, and analyst ratings from
    Financial Modeling Prep. Requires FMP_API_KEY. Free tier: 250 calls/day.
    BEST FOR: Assessing investor confidence — who holds the stock, insider
    buy/sell activity, and analyst consensus (buy/hold/sell).
    USE IN STAGE: BANT Scoring (Stage 4) — Budget and Timing dimensions.

    Args:
        ticker: Stock ticker symbol (e.g. 'META', 'AAPL')

    Returns:
        dict with institutional_holders, insider_trades, analyst_ratings
    """
    settings = get_settings()
    api_key = settings.FMP_API_KEY

    if not api_key:
        return {
            "error": "FMP_API_KEY not configured. Use free alternatives: "
                     "get_market_data for valuation data, or "
                     "duckduckgo_search '[company] institutional holders' or "
                     "'[company] analyst rating'.",
            "ticker": ticker,
        }

    ticker = ticker.strip().upper()
    result = {"ticker": ticker}

    # Fetch institutional holders
    try:
        resp = httpx.get(
            f"{FMP_BASE_URL}/institutional-holder/{ticker}",
            params={"apikey": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        holders = resp.json()

        if isinstance(holders, list):
            result["institutional_holders"] = [
                {
                    "holder": h.get("holder", ""),
                    "shares": h.get("shares"),
                    "date_reported": h.get("dateReported", ""),
                    "change": h.get("change"),
                    "change_percent": h.get("changePercent"),
                }
                for h in holders[:10]
            ]
        else:
            result["institutional_holders"] = []

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "ticker": ticker}
        result["institutional_holders_error"] = str(e)
    except Exception as e:
        result["institutional_holders_error"] = str(e)

    # Fetch insider trades
    try:
        resp = httpx.get(
            f"{FMP_BASE_URL}/insider-trading",
            params={"symbol": ticker, "apikey": api_key, "limit": 10},
            timeout=15,
        )
        resp.raise_for_status()
        trades = resp.json()

        if isinstance(trades, list):
            result["insider_trades"] = [
                {
                    "reporting_name": t.get("reportingName", ""),
                    "transaction_type": t.get("transactionType", ""),
                    "securities_transacted": t.get("securitiesTransacted"),
                    "price": t.get("price"),
                    "transaction_date": t.get("transactionDate", ""),
                }
                for t in trades[:10]
            ]
        else:
            result["insider_trades"] = []

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "ticker": ticker}
        result["insider_trades_error"] = str(e)
    except Exception as e:
        result["insider_trades_error"] = str(e)

    # Fetch analyst ratings / consensus
    try:
        resp = httpx.get(
            f"{FMP_BASE_URL}/analyst-stock-recommendations/{ticker}",
            params={"apikey": api_key, "limit": 5},
            timeout=15,
        )
        resp.raise_for_status()
        ratings = resp.json()

        if isinstance(ratings, list) and ratings:
            latest = ratings[0]
            result["analyst_consensus"] = {
                "date": latest.get("date", ""),
                "analyst_ratings_buy": latest.get("analystRatingsbuy"),
                "analyst_ratings_hold": latest.get("analystRatingsHold"),
                "analyst_ratings_sell": latest.get("analystRatingsSell"),
                "analyst_ratings_strong_buy": latest.get("analystRatingsStrongBuy"),
                "analyst_ratings_strong_sell": latest.get("analystRatingsStrongSell"),
            }
        else:
            result["analyst_consensus"] = {}

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "ticker": ticker}
        result["analyst_consensus_error"] = str(e)
    except Exception as e:
        result["analyst_consensus_error"] = str(e)

    return result
