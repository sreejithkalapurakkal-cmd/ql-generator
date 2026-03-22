"""Post-parse data validation for pipeline stage outputs.

Validates company data, contacts, and scores after JSON parsing at each stage.
Catches hallucinated data, placeholder values, and obvious inconsistencies.
"""

import logging
import re
from urllib.parse import urlparse

from app.tools.retry_utils import httpx_get_with_retry

logger = logging.getLogger(__name__)

# Known placeholder/test domains to reject
PLACEHOLDER_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "test.org",
    "localhost", "placeholder.com", "samplewebsite.com", "domain.com",
    "company.com", "website.com", "companywebsite.com", "mycompany.com",
}

# RFC 5322 simplified email regex
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}"
    r"[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

LINKEDIN_URL_PATTERN = re.compile(
    r"^https?://(?:www\.)?linkedin\.com/in/[\w-]+/?$"
)

# Suspicious company name patterns
SUSPICIOUS_NAME_PATTERNS = [
    re.compile(r"^Company\s*\d+$", re.IGNORECASE),
    re.compile(r"^[A-Z\s]{20,}$"),  # All-caps over 20 chars
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE),  # UUID-like
    re.compile(r"^(Unknown|N/A|None|TBD|Test|Sample|Example)\s*", re.IGNORECASE),
    re.compile(r"^[A-Z]{1,2}\d{5,}$"),  # Code-like strings
]


def validate_company(company: dict) -> tuple[bool, list[str]]:
    """Validate a company dict from agent output.

    Returns:
        (is_valid, list_of_warnings) — is_valid is False if the company
        should be rejected entirely. Warnings are non-fatal issues.
    """
    warnings = []
    name = company.get("name", "")
    website = company.get("website", "")

    # Name validation
    if not name or len(name.strip()) < 2:
        return False, ["Company name is empty or too short"]

    for pattern in SUSPICIOUS_NAME_PATTERNS:
        if pattern.match(name.strip()):
            return False, [f"Suspicious company name pattern: '{name}'"]

    # Website validation
    if website:
        domain = _normalize_domain(website)
        if domain in PLACEHOLDER_DOMAINS:
            return False, [f"Placeholder domain: {domain}"]

    # Numeric validation
    emp = company.get("employee_count")
    if emp is not None:
        try:
            emp = int(emp)
            if emp < 1:
                warnings.append(f"Employee count {emp} < 1, setting to None")
                company["employee_count"] = None
            elif emp > 10_000_000:
                warnings.append(f"Employee count {emp} > 10M, likely hallucinated")
                company["employee_count"] = None
        except (ValueError, TypeError):
            warnings.append(f"Invalid employee count: {emp}")
            company["employee_count"] = None

    rev = company.get("revenue_estimate")
    if rev is not None:
        try:
            rev = float(rev)
            if rev < 0:
                warnings.append(f"Negative revenue {rev}, setting to None")
                company["revenue_estimate"] = None
        except (ValueError, TypeError):
            warnings.append(f"Invalid revenue: {rev}")
            company["revenue_estimate"] = None

    # Inconsistency check: $1B+ revenue with <10 employees
    if emp and rev:
        try:
            emp_val = int(emp)
            rev_val = float(rev)
            if rev_val > 1_000_000_000 and emp_val < 10:
                warnings.append(
                    f"Inconsistent: ${rev_val:,.0f} revenue with only {emp_val} employees"
                )
            if rev_val < 100_000 and emp_val > 10_000:
                warnings.append(
                    f"Inconsistent: ${rev_val:,.0f} revenue with {emp_val} employees"
                )
        except (ValueError, TypeError):
            pass

    return True, warnings


def validate_contact(contact: dict, company_domain: str = "") -> tuple[bool, list[str]]:
    """Validate a contact dict from agent output.

    Returns:
        (is_valid, list_of_warnings)
    """
    warnings = []
    name = contact.get("full_name") or contact.get("name", "")
    email = contact.get("email", "")
    linkedin = contact.get("linkedin_url", "")
    phone = contact.get("phone", "")

    # At least name or email must be present
    if not name and not email:
        return False, ["Contact has neither name nor email"]

    # Name validation
    if name:
        if len(name.strip()) < 3:
            warnings.append(f"Very short contact name: '{name}'")
        # Check for suspicious patterns
        for pattern in SUSPICIOUS_NAME_PATTERNS:
            if pattern.match(name.strip()):
                return False, [f"Suspicious contact name: '{name}'"]

    # Email validation
    if email:
        if not EMAIL_REGEX.match(email):
            warnings.append(f"Invalid email format: {email}")
            contact["email"] = None
        elif company_domain:
            email_domain = email.split("@")[-1].lower()
            norm_company = _normalize_domain(company_domain)
            # Email domain should somewhat match company domain
            # (allow subdomains, common email providers)
            if (email_domain != norm_company and
                    not email_domain.endswith(f".{norm_company}") and
                    email_domain not in ("gmail.com", "yahoo.com", "outlook.com",
                                          "hotmail.com", "protonmail.com")):
                warnings.append(
                    f"Email domain '{email_domain}' doesn't match company '{norm_company}'"
                )

    # LinkedIn URL validation
    if linkedin:
        if not LINKEDIN_URL_PATTERN.match(linkedin):
            # Try to fix common issues
            if "linkedin.com/in/" in linkedin:
                warnings.append(f"LinkedIn URL has extra params: {linkedin}")
            else:
                warnings.append(f"Invalid LinkedIn URL format: {linkedin}")
                contact["linkedin_url"] = None

    # Phone validation (basic length check)
    if phone:
        digits = re.sub(r"[^\d]", "", phone)
        if len(digits) < 7 or len(digits) > 15:
            warnings.append(f"Invalid phone number length ({len(digits)} digits): {phone}")
            contact["phone"] = None

    return True, warnings


def validate_score(score: float | None, field_name: str = "score") -> tuple[float | None, list[str]]:
    """Validate a score value is in the 0-100 range.

    Returns:
        (validated_score, list_of_warnings)
    """
    if score is None:
        return None, []

    warnings = []
    try:
        score = float(score)
    except (ValueError, TypeError):
        return None, [f"Invalid {field_name}: {score}"]

    if score < 0:
        warnings.append(f"{field_name} {score} < 0, clamping to 0")
        score = 0.0
    elif score > 100:
        warnings.append(f"{field_name} {score} > 100, clamping to 100")
        score = 100.0

    return score, warnings


def validate_stage_companies(companies: list[dict]) -> list[dict]:
    """Validate a list of companies from a stage output.

    Removes invalid companies and logs warnings. Returns the filtered list.
    """
    valid = []
    for company in companies:
        is_valid, warnings = validate_company(company)
        if warnings:
            logger.warning(
                f"Validation warnings for '{company.get('name', 'Unknown')}': "
                f"{'; '.join(warnings)}"
            )
        if is_valid:
            valid.append(company)
        else:
            logger.info(
                f"Rejected company '{company.get('name', 'Unknown')}': "
                f"{'; '.join(warnings)}"
            )

    rejected = len(companies) - len(valid)
    if rejected > 0:
        logger.info(f"Validation: rejected {rejected}/{len(companies)} companies")

    return valid


def validate_stage_contacts(
    contacts: list[dict],
    company_domain: str = "",
) -> list[dict]:
    """Validate a list of contacts from a stage output.

    Removes invalid contacts and logs warnings. Returns the filtered list.
    """
    valid = []
    for contact in contacts:
        is_valid, warnings = validate_contact(contact, company_domain)
        if warnings:
            logger.debug(
                f"Contact validation warnings for "
                f"'{contact.get('full_name', contact.get('name', 'Unknown'))}': "
                f"{'; '.join(warnings)}"
            )
        if is_valid:
            valid.append(contact)

    rejected = len(contacts) - len(valid)
    if rejected > 0:
        logger.info(
            f"Contact validation: rejected {rejected}/{len(contacts)} contacts "
            f"for domain={company_domain}"
        )

    return valid


def compute_data_quality_score(company) -> float:
    """Compute a data quality score (0.0-1.0) based on field population.

    Used to sort companies within Stage 2 batches so richest-data companies
    are processed first (they require less agent research effort).

    Works with both Company ORM objects and plain dicts.
    """
    weights = {
        "name": 0.10,
        "website": 0.15,
        "employee_count": 0.20,
        "revenue_estimate": 0.20,
        "industry": 0.10,
        "country": 0.10,
        "description": 0.15,
    }

    score = 0.0
    for field, weight in weights.items():
        if isinstance(company, dict):
            value = company.get(field)
        else:
            value = getattr(company, field, None)
        if value is not None and value != "" and value != 0:
            score += weight

    return round(score, 2)


def _normalize_domain(domain: str) -> str:
    """Normalize a domain for comparison."""
    d = domain.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/")
