from strands import tool


@tool
def get_market_data(ticker: str) -> dict:
    """
    Get real-time market data for a public company using Yahoo Finance. FREE, no API key.
    BEST FOR: Current market cap, PE ratio, revenue TTM, profit margins,
    52-week price range, and valuation multiples.
    USE IN STAGE: BANT Scoring (Stage 4) — Budget dimension.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT')

    Returns:
        dict with current_price, market_cap, pe_ratio, revenue_ttm,
        profit_margins, 52_week_high, 52_week_low, average_volume, dividend_yield
    """
    try:
        import yfinance as yf
    except ImportError:
        return {
            "error": "yfinance package not installed. Install with: pip install yfinance. "
                     "As a fallback, use duckduckgo_search '[company] stock price market cap' "
                     "or get_sec_filings for financial data.",
            "ticker": ticker,
        }

    ticker = ticker.strip().upper()

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return {
                "error": f"No market data found for ticker '{ticker}'. "
                         "Verify the ticker symbol is correct.",
                "ticker": ticker,
            }

        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName", ""),
            "current_price": info.get("regularMarketPrice") or info.get("currentPrice"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue_ttm": info.get("totalRevenue"),
            "profit_margins": info.get("profitMargins"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "average_volume": info.get("averageVolume"),
            "dividend_yield": info.get("dividendYield"),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "employee_count": info.get("fullTimeEmployees"),
            "website": info.get("website", ""),
        }

    except Exception as e:
        return {"error": str(e), "ticker": ticker}
