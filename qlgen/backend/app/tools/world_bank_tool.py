import httpx
from strands import tool
from app.config import get_settings

DEFAULT_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "FP.CPI.TOTL.ZG": "Inflation (consumer prices, annual %)",
    "SL.UEM.TOTL.ZS": "Unemployment (% of total labor force)",
}

# FRED series for US-specific data (Federal Reserve Economic Data)
FRED_US_SERIES = {
    "GDPC1": "Real GDP (Billions of Chained 2017 Dollars)",
    "CPIAUCSL": "Consumer Price Index (All Urban Consumers)",
    "UNRATE": "Unemployment Rate (%)",
}


def _fetch_fred_us() -> dict:
    """Fetch key US economic indicators from FRED API."""
    settings = get_settings()
    fred_key = settings.FRED_API_KEY
    if not fred_key:
        return {}

    results = {}
    for series_id, label in FRED_US_SERIES.items():
        try:
            resp = httpx.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": fred_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 5,
                },
                timeout=10,
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
            values = [
                {"date": o["date"], "value": float(o["value"])}
                for o in obs
                if o.get("value") not in (".", None)
            ]
            results[series_id] = {"label": label, "source": "FRED", "data": values}
        except Exception as e:
            results[series_id] = {"label": label, "source": "FRED", "error": str(e)}

    return results


@tool
def get_economic_indicators(
    country_code: str,
    indicator: str = "",
) -> dict:
    """
    Fetch macro-economic indicators from World Bank (all countries) and FRED
    (US only, more granular). FREE — World Bank needs no key; FRED uses FRED_API_KEY.
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
        dict with indicator data for last 5 years, plus FRED data for US
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

    response = {"country_code": code, "indicators": results}

    # Supplement with FRED data for US (more granular and recent)
    if code == "US" and not indicator:
        fred_data = _fetch_fred_us()
        if fred_data:
            response["fred_indicators"] = fred_data

    return response
