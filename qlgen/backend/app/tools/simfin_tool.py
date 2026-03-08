import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: SimFin API limit reached. Do NOT retry this tool. "
    "Use get_sec_filings or get_market_data as free alternatives for "
    "financial data, or duckduckgo_search '[company] financials revenue'."
)


@tool
def get_financial_statements(ticker: str) -> dict:
    """
    Get standardised financial statements from SimFin. Requires SIMFIN_API_KEY.
    BEST FOR: Clean, comparable income statement, balance sheet, and cash flow
    data across 3000+ companies in a consistent USD format.
    USE IN STAGE: BANT Scoring (Stage 4) — Budget dimension.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL', 'MSFT')

    Returns:
        dict with income_statement, balance_sheet, and cash_flow data
    """
    settings = get_settings()
    api_key = settings.SIMFIN_API_KEY

    if not api_key:
        return {
            "error": "SIMFIN_API_KEY not configured. Use free alternatives: "
                     "get_sec_filings for SEC data or get_market_data for "
                     "Yahoo Finance data.",
            "ticker": ticker,
        }

    ticker = ticker.strip().upper()
    base_url = "https://backend.simfin.com/api/v3/companies/statements"
    headers = {
        "Authorization": f"api-key {api_key}",
        "Accept": "application/json",
    }

    statements = {}

    for statement_type in ["pl", "bs", "cf"]:
        statement_name = {
            "pl": "income_statement",
            "bs": "balance_sheet",
            "cf": "cash_flow",
        }[statement_type]

        try:
            params = {
                "ticker": ticker,
                "statement": statement_type,
                "period": "fy",
                "fyear": 0,  # most recent
            }

            resp = httpx.get(
                base_url,
                params=params,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            # SimFin returns a list of statement entries
            if isinstance(data, list) and data:
                # Extract the most recent statement
                statement = data[0] if isinstance(data[0], dict) else {}
                statements[statement_name] = statement
            else:
                statements[statement_name] = {"note": "No data available"}

        except httpx.HTTPStatusError as e:
            if e.response.status_code in RATE_LIMIT_CODES:
                return {
                    "error": RATE_LIMIT_MSG,
                    "rate_limited": True,
                    "ticker": ticker,
                }
            statements[statement_name] = {"error": str(e)}
        except Exception as e:
            statements[statement_name] = {"error": str(e)}

    return {
        "ticker": ticker,
        **statements,
    }
