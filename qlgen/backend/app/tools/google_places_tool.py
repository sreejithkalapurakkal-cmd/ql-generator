import httpx
from strands import tool
from app.config import get_settings

RATE_LIMIT_CODES = {429, 402, 403}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Google Places API quota exceeded. Do NOT retry this tool. "
    "Switch to free alternatives: use duckduckgo_search to find phone numbers "
    "(search '[company name] phone number' or '[company name] contact'), "
    "and scrape_webpage on the company's contact page."
)


@tool
def get_company_phone(
    company_name: str,
    company_website: str = "",
) -> dict:
    """
    Look up a company's phone number using Google Places API.
    PAID (requires GOOGLE_PLACES_API_KEY). Gracefully handles missing key.
    BEST FOR: Finding verified business phone numbers.
    USE IN STAGE: Contact Enrichment (Stage 3).

    Args:
        company_name: Name of the company to look up
        company_website: Optional company website to improve match accuracy

    Returns:
        dict with 'phone', 'international_phone', 'website', 'name'
    """
    settings = get_settings()
    api_key = settings.GOOGLE_PLACES_API_KEY

    if not api_key:
        return {
            "error": (
                "GOOGLE_PLACES_API_KEY not configured. Use free alternatives instead: "
                "duckduckgo_search '[company] phone number' or "
                "scrape_webpage on the company's /contact page."
            ),
            "phone": None,
        }

    # Build the search input — include website for better matching
    search_input = company_name
    if company_website:
        domain = company_website.replace("https://", "").replace("http://", "").rstrip("/")
        search_input = f"{company_name} {domain}"

    find_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": search_input,
        "inputtype": "textquery",
        "fields": "place_id,name,formatted_phone_number,international_phone_number,website",
        "key": api_key,
    }

    try:
        response = httpx.get(find_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return {
                "error": f"No Google Places match found for '{company_name}'",
                "phone": None,
            }

        place = candidates[0]
        place_id = place.get("place_id")

        # If we got a place_id, fetch details for phone numbers
        if place_id:
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "fields": "name,formatted_phone_number,international_phone_number,website",
                "key": api_key,
            }
            details_resp = httpx.get(details_url, params=details_params, timeout=15)
            details_resp.raise_for_status()
            details = details_resp.json().get("result", {})
        else:
            details = place

        return {
            "name": details.get("name", company_name),
            "phone": details.get("formatted_phone_number"),
            "international_phone": details.get("international_phone_number"),
            "website": details.get("website"),
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        return {"error": str(e), "phone": None}
    except Exception as e:
        return {"error": str(e), "phone": None}
