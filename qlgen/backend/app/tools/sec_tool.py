import httpx
from strands import tool

SEC_HEADERS = {
    "User-Agent": "qlGen Research Bot contact@qlgen.io",
    "Accept": "application/json",
}


@tool
def get_sec_filings(
    company_ticker: str,
    filing_type: str = "10-K",
) -> dict:
    """
    Fetch SEC EDGAR filings for a US public company. FREE, no API key needed.
    BEST FOR: Getting legally verified revenue, net income, debt, and cash flow
    data for US public companies. Most authoritative financial data source.
    USE IN STAGE: BANT Scoring (Stage 4) — Budget dimension.

    Args:
        company_ticker: Stock ticker symbol (e.g. 'AAPL', 'MSFT', 'NVDA')
        filing_type: Type of filing - '10-K' for annual, '10-Q' for quarterly

    Returns:
        dict with recent filings including date, type, and direct URL to filing
    """
    ticker = company_ticker.strip().upper()

    try:
        # Step 1: Resolve ticker to CIK using SEC company tickers endpoint
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        resp = httpx.get(tickers_url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        tickers_data = resp.json()

        cik = None
        company_name = None
        for entry in tickers_data.values():
            if entry.get("ticker", "").upper() == ticker:
                cik = str(entry["cik_str"]).zfill(10)
                company_name = entry.get("title", "")
                break

        if not cik:
            return {
                "error": f"Ticker '{ticker}' not found in SEC EDGAR. "
                         "This tool only works for US public companies.",
                "filings": [],
            }

        # Step 2: Fetch submission history
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        sub_resp = httpx.get(submissions_url, headers=SEC_HEADERS, timeout=15)
        sub_resp.raise_for_status()
        sub_data = sub_resp.json()

        # Step 3: Extract recent filings of the requested type
        recent = sub_data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        filings = []
        for i, form in enumerate(forms):
            if form == filing_type and i < len(dates):
                accession_clean = accessions[i].replace("-", "")
                doc = primary_docs[i] if i < len(primary_docs) else ""
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{cik.lstrip('0')}/{accession_clean}/{doc}"
                )
                filings.append({
                    "filing_type": form,
                    "filing_date": dates[i],
                    "accession_number": accessions[i],
                    "url": filing_url,
                })
                if len(filings) >= 5:
                    break

        # Step 4: Try to fetch XBRL financial facts for key metrics
        financials = {}
        try:
            facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            facts_resp = httpx.get(facts_url, headers=SEC_HEADERS, timeout=15)
            facts_resp.raise_for_status()
            facts = facts_resp.json()

            us_gaap = facts.get("facts", {}).get("us-gaap", {})

            # Extract most recent annual values for key metrics
            metrics = {
                "revenue": [
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues",
                    "SalesRevenueNet",
                ],
                "net_income": ["NetIncomeLoss"],
                "total_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
                "operating_cash_flow": [
                    "NetCashProvidedByOperatingActivities",
                ],
            }

            for metric_name, gaap_keys in metrics.items():
                for key in gaap_keys:
                    if key in us_gaap:
                        units = us_gaap[key].get("units", {})
                        usd_values = units.get("USD", [])
                        # Filter to annual (10-K) filings
                        annual = [
                            v for v in usd_values
                            if v.get("form") == "10-K" and v.get("val") is not None
                        ]
                        if annual:
                            latest = sorted(annual, key=lambda x: x.get("end", ""))[-1]
                            financials[metric_name] = {
                                "value": latest["val"],
                                "period_end": latest.get("end", ""),
                                "period_start": latest.get("start", ""),
                            }
                            break

        except Exception:
            pass  # XBRL data is supplementary, filings list is still useful

        return {
            "company": company_name or ticker,
            "ticker": ticker,
            "cik": cik,
            "filing_type": filing_type,
            "filings": filings,
            "financials": financials,
        }

    except Exception as e:
        return {"error": str(e), "filings": []}
