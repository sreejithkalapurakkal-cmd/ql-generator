"""Evaboot (LinkedIn Sales Navigator) tools for prospect extraction, email finding, and validation.

Evaboot links to a Sales Navigator account and exposes REST APIs for:
- Profile extraction from Sales Navigator search/list URLs (async, 1 credit/profile)
- Email finding (1 credit/person) and validation (0.5 credit/email)
- Search URL generation from natural language (free, 100/day)

API docs: https://docs.evaboot.com/
Auth: Bearer token in Authorization header.
All bulk operations are async (return 202, poll for results or use webhooks).
"""

import logging
import time
import httpx
from strands import tool
from app.config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_CODES = {429, 402}
RATE_LIMIT_MSG = (
    "RATE_LIMITED: Evaboot API quota exceeded or insufficient credits. "
    "Do NOT retry this tool. Switch to other discovery tools: "
    "apollo_company_search, exa_search, or duckduckgo_search."
)

_TIMEOUT = 30


def _headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Token {settings.EVABOOT_API_KEY}",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return get_settings().EVABOOT_BASE_URL.rstrip("/")


# ── Quota / Credits ─────────────────────────────────────────────

@tool
def evaboot_check_quota() -> dict:
    """
    Check Evaboot account quota: available credits, daily extraction limit, and Sales Navigator accounts.
    BEST FOR: Pre-flight credit check before starting an extraction.
    USE IN STAGE: Pre-pipeline validation

    Returns:
        dict with 'daily_limit', 'used_today', 'remaining', 'credits', 'salesnavs'
    """
    try:
        response = httpx.get(
            f"{_base_url()}/v1/quota/",
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        if status in (401, 403):
            return {"error": f"Evaboot authentication error ({status}). Check API key."}
        return {"error": f"Evaboot quota check failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot quota check failed: {e}"}


# ── Extraction (async) ──────────────────────────────────────────

@tool
def evaboot_extract_from_url(
    linkedin_url: str,
    search_name: str,
    enrich_email: str = "all",
) -> dict:
    """
    Start an async extraction of LinkedIn profiles from a Sales Navigator search or list URL.
    BEST FOR: Bulk prospect extraction from Sales Navigator (1 credit/profile + 1 credit/email if enriched).
    USE IN STAGE: Company Discovery (Stage 1) when discovery_mode includes Sales Navigator.

    This is ASYNC — returns a job ID. Use evaboot_get_extraction_status to poll progress,
    then evaboot_get_extraction_results to get the data.

    IMPORTANT: The user must narrow their Sales Navigator search BEFORE providing the URL.
    A broad search can consume hundreds of credits.

    Args:
        linkedin_url: Sales Navigator search URL or saved list URL
        search_name: A descriptive name for the extraction job
        enrich_email: Email enrichment mode — "none", "matching" (only filtered prospects), or "all" (all prospects). Default "all".

    Returns:
        dict with 'id' (extraction job ID), 'status' ('pending'), and job metadata
    """
    payload = {
        "linkedin_url": linkedin_url,
        "search_name": search_name,
        "enrich_email": enrich_email if enrich_email in ("none", "matching", "all") else "all",
    }

    try:
        response = httpx.post(
            f"{_base_url()}/v1/extractions/url/",
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        # 202 Accepted is the expected success response for async operations
        if response.status_code == 202:
            return response.json()
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = ""
        try:
            body = e.response.text[:500]
        except Exception:
            pass
        logger.warning(f"Evaboot extraction HTTP {status}: {body}")

        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        if status in (401, 403):
            return {"error": f"Evaboot authentication error ({status}). Check API key or Sales Navigator cookies."}
        if status == 400:
            return {"error": f"Evaboot rejected the extraction request. Check the Sales Navigator URL. Details: {body}"}
        return {"error": f"Evaboot extraction failed: HTTP {status} — {body}"}
    except Exception as e:
        return {"error": f"Evaboot extraction failed: {e}"}


@tool
def evaboot_get_extraction_status(extraction_id: str) -> dict:
    """
    Poll the status of an Evaboot extraction job.
    BEST FOR: Checking progress of an async extraction started with evaboot_extract_from_url.
    USE IN STAGE: Company Discovery (Stage 1) — poll until status is 'complete' or 'failed'.

    Args:
        extraction_id: The extraction job ID returned by evaboot_extract_from_url

    Returns:
        dict with 'id', 'status' ('pending'/'running'/'complete'/'failed'), and progress info
    """
    try:
        response = httpx.get(
            f"{_base_url()}/v1/extractions/{extraction_id}/",
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            return {"error": f"Extraction {extraction_id} not found."}
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        return {"error": f"Evaboot status check failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot status check failed: {e}"}


@tool
def evaboot_get_extraction_results(extraction_id: str) -> dict:
    """
    Get the results of a completed Evaboot extraction.
    BEST FOR: Retrieving prospect data after extraction status is 'complete'.
    USE IN STAGE: Company Discovery (Stage 1)

    Args:
        extraction_id: The extraction job ID

    Returns:
        dict with 'prospects' list containing profile data (name, company, title,
        email, LinkedIn URL, location, etc.) and 'total_count'
    """
    try:
        response = httpx.get(
            f"{_base_url()}/v1/extractions/{extraction_id}/",
            headers=_headers(),
            timeout=60,  # Larger timeout for potentially large result sets
        )
        response.raise_for_status()
        data = response.json()

        # Extract and trim prospect data to reduce context window usage
        prospects = data.get("prospects", data.get("results", []))
        trimmed = []
        for p in prospects:
            trimmed.append({
                "first_name": p.get("first_name"),
                "last_name": p.get("last_name"),
                "full_name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "headline": (p.get("headline") or "")[:200],
                "current_company": p.get("current_company") or p.get("company_name"),
                "current_company_domain": p.get("current_company_domain") or p.get("company_domain"),
                "current_title": p.get("current_title") or p.get("job_title"),
                "email": p.get("email"),
                "email_validity": p.get("email_validity"),
                "phone": p.get("phone"),
                "linkedin_url": p.get("linkedin_url") or p.get("profile_url"),
                "location": p.get("location"),
                "company_industry": p.get("company_industry") or p.get("industry"),
                "company_size": p.get("company_size") or p.get("employee_count"),
                "company_description": (p.get("company_description") or "")[:300],
                "company_website": p.get("company_website") or p.get("company_domain"),
                "company_location": p.get("company_location"),
                "company_founded": p.get("company_founded"),
                "company_specialties": p.get("company_specialties"),
                "company_linkedin_url": p.get("company_linkedin_url"),
            })

        return {
            "prospects": trimmed,
            "total_count": len(trimmed),
            "extraction_id": extraction_id,
            "status": data.get("status", "complete"),
        }
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            return {"error": f"Extraction {extraction_id} not found.", "prospects": []}
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True, "prospects": []}
        return {"error": f"Evaboot results failed: HTTP {status}", "prospects": []}
    except Exception as e:
        return {"error": f"Evaboot results failed: {e}", "prospects": []}


# ── Single profile extraction (sync) ────────────────────────────

@tool
def evaboot_extract_single_profile(profile_url: str) -> dict:
    """
    Extract data from a single LinkedIn Sales Navigator profile (synchronous).
    BEST FOR: Quick enrichment of a single prospect. Costs 1 credit.
    USE IN STAGE: Contact Discovery (Stage 4) for enriching individual contacts.

    Args:
        profile_url: LinkedIn profile URL or Sales Navigator profile URL

    Returns:
        dict with prospect profile data (name, company, title, email, etc.)
    """
    payload = {
        "profile_ids": [profile_url],
        "search_name": "single_profile_extraction",
    }

    try:
        response = httpx.post(
            f"{_base_url()}/v1/extractions/profiles/",
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        if response.status_code == 202:
            return response.json()
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        if status in (401, 403):
            return {"error": f"Evaboot authentication error ({status}). Check API key or Sales Navigator cookies."}
        return {"error": f"Evaboot single profile extraction failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot single profile extraction failed: {e}"}


# ── Email Finding (async) ───────────────────────────────────────

@tool
def evaboot_find_email(
    first_name: str,
    last_name: str,
    company_name: str,
    company_domain: str = None,
) -> dict:
    """
    Find a professional email address for a person. Costs 1 credit per person.
    BEST FOR: Finding contact emails when you have name + company.
    USE IN STAGE: Contact Discovery (Stage 4)

    This is ASYNC — creates a finding job. For single lookups, poll the returned job ID.

    Args:
        first_name: Person's first name
        last_name: Person's last name
        company_name: Company name the person works at
        company_domain: Company domain (e.g., "acme.com") — improves accuracy if provided

    Returns:
        dict with job 'id', 'status', and when complete: 'prospects' with email results
    """
    prospect = {
        "first_name": first_name,
        "last_name": last_name,
        "company_name": company_name,
    }
    if company_domain:
        prospect["company_domain"] = company_domain

    payload = {
        "job_name": f"email_{first_name}_{last_name}_{company_name}",
        "prospects": [prospect],
    }

    try:
        response = httpx.post(
            f"{_base_url()}/v1/email-finder/",
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        if response.status_code == 202:
            return response.json()
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        if status in (401, 403):
            return {"error": f"Evaboot authentication error ({status}). Check API key."}
        return {"error": f"Evaboot email finder failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot email finder failed: {e}"}


@tool
def evaboot_get_email_job_results(job_id: str) -> dict:
    """
    Get results of an Evaboot email finder job.
    BEST FOR: Retrieving email results after evaboot_find_email.
    USE IN STAGE: Contact Discovery (Stage 4)

    Args:
        job_id: The email finder job ID

    Returns:
        dict with 'prospects' containing email results, 'status'
    """
    try:
        response = httpx.get(
            f"{_base_url()}/v1/email-finder/{job_id}/",
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            return {"error": f"Email finder job {job_id} not found."}
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        return {"error": f"Evaboot email job results failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot email job results failed: {e}"}


# ── Email Validation (async) ────────────────────────────────────

@tool
def evaboot_validate_email(email: str) -> dict:
    """
    Validate a professional email address. Costs 0.5 credits per email.
    BEST FOR: Verifying email deliverability before outreach.
    USE IN STAGE: Contact Discovery (Stage 4) — validate emails found by other tools.

    This is ASYNC — creates a validation job. Poll the returned job ID for results.

    Args:
        email: Email address to validate

    Returns:
        dict with job 'id', 'status', and when complete: validation result
            ('safe' = high confidence, 'riskier' = lower confidence)
    """
    payload = {
        "job_name": f"validate_{email}",
        "prospects": [{"email": email}],
    }

    try:
        response = httpx.post(
            f"{_base_url()}/v1/email-validation/",
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        if response.status_code == 202:
            return response.json()
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        return {"error": f"Evaboot email validation failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot email validation failed: {e}"}


@tool
def evaboot_get_validation_results(job_id: str) -> dict:
    """
    Get results of an Evaboot email validation job.
    BEST FOR: Retrieving validation results after evaboot_validate_email.
    USE IN STAGE: Contact Discovery (Stage 4)

    Args:
        job_id: The email validation job ID

    Returns:
        dict with 'prospects' containing email_validity ('safe'/'riskier'), 'status'
    """
    try:
        response = httpx.get(
            f"{_base_url()}/v1/email-validation/{job_id}/",
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 404:
            return {"error": f"Validation job {job_id} not found."}
        if status in RATE_LIMIT_CODES:
            return {"error": RATE_LIMIT_MSG, "rate_limited": True}
        return {"error": f"Evaboot validation results failed: HTTP {status}"}
    except Exception as e:
        return {"error": f"Evaboot validation results failed: {e}"}
