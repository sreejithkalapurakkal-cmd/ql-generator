import logging
import httpx
from strands import tool
from app.config import get_settings

logger = logging.getLogger(__name__)

SIMFIN_BASE_URL = "https://backend.simfin.com/api/v3"

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: SimFin API quota exceeded. Do NOT retry this tool. "
    "Use get_sec_filings or get_market_data instead."
)


@tool
def get_financial_statements(
    ticker: str,
    statement_type: str = "all",
    period: str = "annual",
    limit: int = 3,
) -> dict:
    """
    Retrieve financial statements from SimFin for public companies.
    BEST FOR: Getting detailed income statement, balance sheet, and cash flow data
    to assess company financial health, revenue trends, and budget capacity.
    USE IN STAGE: Signal Research (Stage 3) — budget dimension

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
        statement_type: Type of statement — "income", "balance", "cashflow", or "all"
        period: Reporting period — "annual" (default), "quarterly", or "ttm" (trailing twelve months)
        limit: Number of periods to return (default 3, max 5)

    Returns:
        dict with financial data including revenue, net_income, total_assets,
        total_debt, operating_cash_flow, free_cash_flow, and growth rates
    """
    settings = get_settings()
    if not settings.SIMFIN_API_KEY:
        return {"error": "SimFin API key not configured. Use get_sec_filings or get_market_data instead.", "data": {}}

    headers = {
        "Authorization": f"api-key {settings.SIMFIN_API_KEY}",
        "Accept": "application/json",
    }

    limit = min(limit, 5)
    results = {}

    statement_types = (
        ["income", "balance", "cashflow"]
        if statement_type == "all"
        else [statement_type]
    )

    # Map statement types to SimFin endpoints
    endpoint_map = {
        "income": "income",
        "balance": "balance",
        "cashflow": "cashflow",
    }

    for st in statement_types:
        endpoint = endpoint_map.get(st)
        if not endpoint:
            continue

        url = f"{SIMFIN_BASE_URL}/companies/{ticker}/statements/{endpoint}"
        params = {
            "period": "fy" if period == "annual" else ("q1,q2,q3,q4" if period == "quarterly" else "ttm"),
            "limit": limit,
        }

        try:
            response = httpx.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and data:
                results[st] = data[:limit]
            elif isinstance(data, dict):
                results[st] = data
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RATE_LIMIT_CODES:
                return {"error": RATE_LIMIT_MSG, "rate_limited": True, "data": {}}
            resp_body = ""
            try:
                resp_body = e.response.text[:300]
            except Exception:
                pass
            logger.warning(f"SimFin {st} HTTP {e.response.status_code}: {resp_body}")
            results[st] = {"error": f"HTTP {e.response.status_code}: {resp_body}"}
        except Exception as e:
            logger.warning(f"SimFin {st} error: {e}")
            results[st] = {"error": str(e)}

    if not results:
        return {"error": f"No financial data found for ticker '{ticker}'", "data": {}}

    # Extract key metrics from income statement for quick access
    summary = {"ticker": ticker, "period": period}
    income_data = results.get("income")
    if isinstance(income_data, list) and income_data:
        latest = income_data[0] if isinstance(income_data[0], dict) else {}
        summary["revenue"] = latest.get("Revenue") or latest.get("revenue")
        summary["net_income"] = latest.get("Net Income") or latest.get("netIncome")
        summary["gross_profit"] = latest.get("Gross Profit") or latest.get("grossProfit")
        summary["operating_income"] = latest.get("Operating Income (Loss)") or latest.get("operatingIncome")

        # Calculate revenue growth if multiple periods
        if len(income_data) >= 2:
            curr_rev = latest.get("Revenue") or latest.get("revenue")
            prev = income_data[1] if isinstance(income_data[1], dict) else {}
            prev_rev = prev.get("Revenue") or prev.get("revenue")
            if curr_rev and prev_rev and prev_rev > 0:
                summary["revenue_growth_pct"] = round((curr_rev - prev_rev) / prev_rev * 100, 1)

    balance_data = results.get("balance")
    if isinstance(balance_data, list) and balance_data:
        latest = balance_data[0] if isinstance(balance_data[0], dict) else {}
        summary["total_assets"] = latest.get("Total Assets") or latest.get("totalAssets")
        summary["total_debt"] = latest.get("Total Debt") or latest.get("totalDebt")
        summary["total_equity"] = latest.get("Total Equity") or latest.get("totalEquity")
        summary["cash"] = latest.get("Cash, Cash Equivalents & Short Term Investments") or latest.get("cash")

    cashflow_data = results.get("cashflow")
    if isinstance(cashflow_data, list) and cashflow_data:
        latest = cashflow_data[0] if isinstance(cashflow_data[0], dict) else {}
        summary["operating_cashflow"] = latest.get("Net Cash from Operating Activities") or latest.get("operatingCashFlow")
        summary["capex"] = latest.get("Capital Expenditures") or latest.get("capitalExpenditures")
        op_cf = summary.get("operating_cashflow")
        capex = summary.get("capex")
        if op_cf is not None and capex is not None:
            summary["free_cash_flow"] = op_cf + capex  # capex is typically negative

    return {
        "summary": {k: v for k, v in summary.items() if v is not None},
        "statements": results,
    }
