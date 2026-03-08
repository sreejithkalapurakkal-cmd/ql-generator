import httpx
from strands import tool

DEFAULT_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "FP.CPI.TOTL.ZG": "Inflation (consumer prices, annual %)",
    "SL.UEM.TOTL.ZS": "Unemployment (% of total labor force)",
}


@tool
def get_economic_indicators(
    country_code: str,
    indicator: str = "",
) -> dict:
    """
    Fetch macro-economic indicators from the World Bank. FREE, no API key needed.
    BEST FOR: Market sizing and macro context — GDP, inflation, unemployment rates
    for a company's home market. Returns data for the last 5 years.
    USE IN STAGE: BANT Scoring (Stage 4) — Budget and Timing dimensions.

    Args:
        country_code: ISO 2-letter country code (e.g. 'US', 'IN', 'GB', 'DE')
        indicator: World Bank indicator code. If empty, fetches GDP, inflation,
                   and unemployment. Common codes:
                   NY.GDP.MKTP.CD (GDP), FP.CPI.TOTL.ZG (inflation),
                   SL.UEM.TOTL.ZS (unemployment), NY.GDP.MKTP.KD.ZG (GDP growth)

    Returns:
        dict with indicator data for last 5 years
    """
    code = country_code.strip().upper()

    indicators_to_fetch = (
        {indicator: indicator} if indicator
        else DEFAULT_INDICATORS
    )

    results = {}

    for ind_code, ind_label in indicators_to_fetch.items():
        try:
            url = (
                f"https://api.worldbank.org/v2/country/{code}"
                f"/indicator/{ind_code}"
            )
            params = {
                "format": "json",
                "per_page": 5,
                "mrv": 5,
            }

            resp = httpx.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # World Bank API returns [metadata, data_array]
            if not isinstance(data, list) or len(data) < 2:
                results[ind_code] = {"label": ind_label, "error": "No data returned"}
                continue

            entries = data[1] or []
            values = []
            for entry in entries:
                if entry.get("value") is not None:
                    values.append({
                        "year": entry.get("date", ""),
                        "value": entry["value"],
                    })

            results[ind_code] = {
                "label": ind_label,
                "country": entries[0].get("country", {}).get("value", code) if entries else code,
                "data": values,
            }

        except Exception as e:
            results[ind_code] = {"label": ind_label, "error": str(e)}

    return {
        "country_code": code,
        "indicators": results,
    }
