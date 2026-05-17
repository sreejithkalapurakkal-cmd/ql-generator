"""Contact enrichment service for tracked companies.

Reuses existing pipeline tools (Apollo, find_executives, DuckDuckGo)
to discover decision-maker contacts for companies in tracking lists.
Results are stored in CompanyKnowledgeBase.best_known_contacts.
"""
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.models.tracking_list import TrackingList
from app.models.tracking_list_membership import TrackingListMembership

logger = logging.getLogger(__name__)

# Default target roles if none specified
DEFAULT_TARGET_ROLES = [
    "CEO", "CTO", "COO", "CIO", "CFO", "CRO",
    "VP Engineering", "VP Product", "VP Sales",
    "Head of Engineering", "Head of Product",
    "Founder", "Co-Founder", "President",
    "Director of Engineering", "Director of IT",
]


async def enrich_company_contacts(
    db: AsyncSession,
    company_kb_id: UUID,
    target_roles: list[str] | None = None,
    event_emitter=None,
) -> dict:
    """Discover and enrich contacts for a single tracked company.

    Uses multiple tools in sequence:
    1. Apollo People Search (seniority + title queries)
    2. Find Company Executives (multi-method scraping)
    3. LinkedIn Profile Search (DDG site:linkedin.com)
    4. Team Page Scraping (company website /team, /about pages)
    5. Exa Contact Search (semantic web search for leadership)

    Args:
        event_emitter: Optional async callable(event_type: str, data: dict) for
            emitting granular progress events (tool_start, tool_result).

    Returns dict with contacts list and metadata.
    """
    result = await db.execute(
        select(CompanyKnowledgeBase).where(CompanyKnowledgeBase.id == company_kb_id)
    )
    kb = result.scalar_one_or_none()
    if not kb:
        return {"error": "Company not found", "contacts": []}

    company_name = kb.canonical_name or kb.normalized_domain
    domain = kb.normalized_domain or ""
    roles = target_roles or DEFAULT_TARGET_ROLES
    industry = kb.industry or ""

    async def _emit(event_type: str, data: dict):
        if event_emitter:
            await event_emitter(event_type, data)

    all_contacts: list[dict] = []

    # Method 1: Apollo People Search
    await _emit("tool_start", {
        "tool": "apollo_people_search",
        "label": "Apollo People Search",
        "company_name": company_name,
    })
    apollo_contacts = await _search_apollo(company_name, domain, roles)
    await _emit("tool_result", {
        "tool": "apollo_people_search",
        "label": "Apollo People Search",
        "contacts_found": len(apollo_contacts),
        "company_name": company_name,
    })
    all_contacts.extend(apollo_contacts)

    # Method 2: Find Company Executives (multi-method scraping)
    await _emit("tool_start", {
        "tool": "find_executives",
        "label": "Executive Finder",
        "company_name": company_name,
    })
    exec_contacts = await _find_executives(company_name, domain, roles, industry)
    await _emit("tool_result", {
        "tool": "find_executives",
        "label": "Executive Finder",
        "contacts_found": len(exec_contacts),
        "company_name": company_name,
    })
    all_contacts.extend(exec_contacts)

    # Method 3: LinkedIn Profile Search
    await _emit("tool_start", {
        "tool": "find_linkedin_profiles",
        "label": "LinkedIn Profile Search",
        "company_name": company_name,
    })
    linkedin_contacts = await _search_linkedin_profiles(company_name, roles)
    await _emit("tool_result", {
        "tool": "find_linkedin_profiles",
        "label": "LinkedIn Profile Search",
        "contacts_found": len(linkedin_contacts),
        "company_name": company_name,
    })
    all_contacts.extend(linkedin_contacts)

    # Method 4: Team Page Scraping
    if domain:
        await _emit("tool_start", {
            "tool": "scrape_team_page",
            "label": "Team Page Scraper",
            "company_name": company_name,
        })
        team_contacts = await _scrape_team_page(domain)
        await _emit("tool_result", {
            "tool": "scrape_team_page",
            "label": "Team Page Scraper",
            "contacts_found": len(team_contacts),
            "company_name": company_name,
        })
        all_contacts.extend(team_contacts)

    # Method 5: Exa Contact Search
    await _emit("tool_start", {
        "tool": "exa_search_contacts",
        "label": "Exa Contact Search",
        "company_name": company_name,
    })
    exa_contacts = await _search_exa_contacts(company_name, domain, roles)
    await _emit("tool_result", {
        "tool": "exa_search_contacts",
        "label": "Exa Contact Search",
        "contacts_found": len(exa_contacts),
        "company_name": company_name,
    })
    all_contacts.extend(exa_contacts)

    # Deduplicate contacts
    deduped = _deduplicate_contacts(all_contacts)

    # Merge with existing contacts from KB
    existing = kb.best_known_contacts or []
    merged = _merge_contacts(existing, deduped)

    # Sort by confidence (highest first), take top 20
    merged.sort(key=lambda c: c.get("confidence", 0), reverse=True)
    merged = merged[:20]

    # Update KB record
    kb.best_known_contacts = merged
    kb.last_enriched_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "company_kb_id": str(company_kb_id),
        "company_name": company_name,
        "contacts_found": len(deduped),
        "total_contacts": len(merged),
        "contacts": merged,
    }


async def bulk_enrich_list(
    db: AsyncSession,
    list_id: UUID,
    user_id: UUID,
    target_roles: list[str] | None = None,
    max_companies: int = 20,
) -> dict:
    """Enrich contacts for all companies in a tracking list.

    Returns summary of enrichment results.
    """
    # Verify list ownership
    list_result = await db.execute(
        select(TrackingList).where(
            TrackingList.id == list_id,
            TrackingList.user_id == user_id,
            TrackingList.is_active == True,
        )
    )
    tracking_list = list_result.scalar_one_or_none()
    if not tracking_list:
        return {"error": "Tracking list not found"}

    # Get members
    members_result = await db.execute(
        select(TrackingListMembership).where(
            TrackingListMembership.tracking_list_id == list_id,
        ).limit(max_companies)
    )
    members = list(members_result.scalars().all())

    results = []
    for member in members:
        member.enrichment_status = "in_progress"
        await db.flush()

        try:
            enrichment = await enrich_company_contacts(
                db, member.company_kb_id, target_roles,
            )
            member.enrichment_status = "enriched"
            results.append({
                "company_kb_id": str(member.company_kb_id),
                "status": "enriched",
                "contacts_found": enrichment.get("contacts_found", 0),
                "total_contacts": enrichment.get("total_contacts", 0),
            })
        except Exception as e:
            logger.warning(f"Enrichment failed for {member.company_kb_id}: {e}")
            member.enrichment_status = "failed"
            results.append({
                "company_kb_id": str(member.company_kb_id),
                "status": "failed",
                "error": str(e),
            })

    await db.flush()

    enriched = sum(1 for r in results if r["status"] == "enriched")
    total_contacts = sum(r.get("total_contacts", 0) for r in results)

    return {
        "list_id": str(list_id),
        "companies_processed": len(results),
        "companies_enriched": enriched,
        "total_contacts_found": total_contacts,
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────
# Tool wrappers
# ──────────────────────────────────────────────────────────────────

async def _search_apollo(
    company_name: str,
    domain: str,
    target_roles: list[str],
) -> list[dict]:
    """Search Apollo for contacts at a company.

    Runs two queries for maximum coverage:
    1. Seniority-based (c_suite, vp, director, manager)
    2. Title-based (specific target roles like CEO, CTO, VP Engineering)
    """
    contacts = []
    try:
        from app.tools.apollo_tool import apollo_people_search

        # Query 1: Seniority-based — broad sweep
        raw = await asyncio.to_thread(
            apollo_people_search,
            company_name=company_name,
            company_domain=domain,
            seniorities=["c_suite", "vp", "director", "manager"],
            per_page=25,
        )
        if isinstance(raw, dict) and not raw.get("error"):
            for person in raw.get("people", []):
                contact = _normalize_apollo_contact(person)
                if contact:
                    contacts.append(contact)

        # Query 2: Title-based — catches people seniority tags miss
        if target_roles:
            raw2 = await asyncio.to_thread(
                apollo_people_search,
                company_name=company_name,
                company_domain=domain,
                titles=target_roles[:8],
                per_page=25,
            )
            if isinstance(raw2, dict) and not raw2.get("error"):
                for person in raw2.get("people", []):
                    contact = _normalize_apollo_contact(person)
                    if contact:
                        contacts.append(contact)
    except Exception as e:
        logger.warning(f"Apollo people search error for {company_name}: {e}")

    return contacts


async def _find_executives(
    company_name: str,
    domain: str,
    target_roles: list[str],
    industry: str,
) -> list[dict]:
    """Use the multi-method executive finder."""
    contacts = []
    try:
        from app.tools.find_executives_tool import find_company_executives
        raw = await asyncio.to_thread(
            find_company_executives,
            company_name=company_name,
            company_domain=domain,
            target_roles=target_roles[:10],
            industry_hint=industry,
        )
        if isinstance(raw, dict):
            for person in raw.get("executives", raw.get("contacts", [])):
                contact = _normalize_exec_contact(person)
                if contact:
                    contacts.append(contact)
    except Exception as e:
        logger.warning(f"Executive finder error for {company_name}: {e}")

    return contacts


async def _search_linkedin_profiles(
    company_name: str,
    target_roles: list[str],
) -> list[dict]:
    """Search LinkedIn for decision-maker profiles via DuckDuckGo."""
    contacts = []
    try:
        from app.tools.linkedin_search_tool import find_linkedin_profiles
        raw = await asyncio.to_thread(
            find_linkedin_profiles,
            company_name=company_name,
            titles=target_roles[:6],
        )
        if isinstance(raw, dict):
            for profile in raw.get("profiles", []):
                name = (profile.get("name") or "").strip()
                if not name or len(name) < 3:
                    continue
                parts = name.split(None, 1)
                contacts.append({
                    "full_name": name,
                    "first_name": parts[0] if parts else "",
                    "last_name": parts[1] if len(parts) > 1 else "",
                    "designation": profile.get("title_searched", ""),
                    "email": None,
                    "phone": None,
                    "linkedin_url": profile.get("linkedin_url"),
                    "city": None,
                    "source": "linkedin_search",
                    "confidence": 0.35,
                })
    except Exception as e:
        logger.warning(f"LinkedIn profile search error for {company_name}: {e}")
    return contacts


async def _scrape_team_page(domain: str) -> list[dict]:
    """Scrape company team page for email addresses."""
    contacts = []
    try:
        from app.tools.team_scraper_tool import scrape_team_page
        raw = await asyncio.to_thread(
            scrape_team_page,
            company_website=domain,
        )
        if isinstance(raw, dict):
            for email in raw.get("emails", []):
                prefix = email.split("@")[0]
                # Infer name from email prefix (first.last@domain)
                name_parts = prefix.replace(".", " ").replace("_", " ").replace("-", " ").split()
                if len(name_parts) >= 2:
                    full_name = " ".join(p.capitalize() for p in name_parts)
                    contacts.append({
                        "full_name": full_name,
                        "first_name": name_parts[0].capitalize(),
                        "last_name": name_parts[-1].capitalize(),
                        "designation": None,
                        "email": email,
                        "phone": None,
                        "linkedin_url": None,
                        "city": None,
                        "source": "team_page_scrape",
                        "confidence": 0.4,
                    })
    except Exception as e:
        logger.warning(f"Team page scrape error for {domain}: {e}")
    return contacts


async def _search_exa_contacts(
    company_name: str,
    domain: str,
    target_roles: list[str],
) -> list[dict]:
    """Search Exa for decision-maker mentions."""
    contacts = []
    try:
        from app.config import get_settings
        settings = get_settings()
        if not settings.EXA_API_KEY:
            return []

        from app.tools.exa_tool import exa_search
        import re

        role_terms = " OR ".join(target_roles[:5])
        raw = await asyncio.to_thread(
            exa_search,
            query=f"{company_name} {role_terms} leadership team",
            num_results=10,
        )
        if isinstance(raw, dict) and not raw.get("rate_limited") and not raw.get("error"):
            for result in raw.get("results", []):
                text = result.get("text", "") or ""
                title = result.get("title", "") or ""
                combined = f"{title} {text}"
                # Extract "Name, Title" patterns
                name_pattern = re.findall(
                    r"([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"
                    r"[,\s]+(?:CEO|CTO|COO|CIO|CFO|CRO|VP|Director|Head|Founder|President|Chief)",
                    combined,
                )
                for name in name_pattern[:3]:
                    parts = name.strip().split(None, 1)
                    contacts.append({
                        "full_name": name.strip(),
                        "first_name": parts[0] if parts else "",
                        "last_name": parts[1] if len(parts) > 1 else "",
                        "designation": None,
                        "email": None,
                        "phone": None,
                        "linkedin_url": None,
                        "city": None,
                        "source": "exa_search",
                        "confidence": 0.25,
                    })
    except Exception as e:
        logger.warning(f"Exa contact search error for {company_name}: {e}")
    return contacts


# ──────────────────────────────────────────────────────────────────
# Contact normalization and deduplication
# ──────────────────────────────────────────────────────────────────

def _normalize_apollo_contact(person: dict) -> dict | None:
    """Normalize an Apollo person record to our contact format."""
    name = person.get("name") or ""
    first = person.get("first_name", "")
    last = person.get("last_name", "")
    if not name and not (first or last):
        return None

    full_name = name or f"{first} {last}".strip()

    email = person.get("email")
    phone_raw = person.get("phone_numbers", [])
    phone = phone_raw[0].get("sanitized_number", "") if phone_raw else ""
    linkedin = person.get("linkedin_url", "")

    title = person.get("title", "")
    city = person.get("city", "")

    # Confidence based on data completeness
    confidence = 0.3
    if email:
        confidence += 0.3
    if phone:
        confidence += 0.15
    if linkedin:
        confidence += 0.2
    if title:
        confidence += 0.05

    return {
        "full_name": full_name,
        "first_name": first,
        "last_name": last,
        "designation": title,
        "email": email,
        "phone": phone or None,
        "linkedin_url": linkedin or None,
        "city": city or None,
        "source": "apollo",
        "confidence": round(confidence, 2),
    }


def _normalize_exec_contact(person: dict) -> dict | None:
    """Normalize a find_executives result to our contact format."""
    name = person.get("name") or person.get("full_name") or ""
    if not name:
        return None

    parts = name.split(None, 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""

    title = person.get("title") or person.get("role") or person.get("designation") or ""
    email = person.get("email")
    linkedin = person.get("linkedin_url") or person.get("linkedin") or ""
    phone = person.get("phone")

    confidence = 0.2
    if email:
        confidence += 0.3
    if linkedin:
        confidence += 0.2
    if phone:
        confidence += 0.1

    # Higher confidence for multi-source contacts
    sources = person.get("sources", [])
    if len(sources) >= 2:
        confidence = min(confidence + 0.15, 0.95)

    return {
        "full_name": name,
        "first_name": first,
        "last_name": last,
        "designation": title,
        "email": email or None,
        "phone": phone or None,
        "linkedin_url": linkedin or None,
        "city": person.get("city"),
        "source": "find_executives",
        "confidence": round(confidence, 2),
    }


def _deduplicate_contacts(contacts: list[dict]) -> list[dict]:
    """Deduplicate contacts by LinkedIn URL, then email, then normalized name."""
    seen_linkedin: set[str] = set()
    seen_email: set[str] = set()
    seen_name: set[str] = set()
    deduped: list[dict] = []

    for contact in contacts:
        linkedin = (contact.get("linkedin_url") or "").strip().lower().rstrip("/")
        email = (contact.get("email") or "").strip().lower()
        name = _normalize_name(contact.get("full_name", ""))

        # Check for duplicates
        if linkedin and linkedin in seen_linkedin:
            # Merge data into existing
            _merge_into_existing(deduped, contact, "linkedin_url", linkedin)
            continue
        if email and email in seen_email:
            _merge_into_existing(deduped, contact, "email", email)
            continue
        if name and name in seen_name:
            _merge_into_existing(deduped, contact, "full_name", name)
            continue

        # New contact
        if linkedin:
            seen_linkedin.add(linkedin)
        if email:
            seen_email.add(email)
        if name:
            seen_name.add(name)
        deduped.append(contact)

    return deduped


def _normalize_name(name: str) -> str:
    """Normalize a name for dedup: lowercase, strip middle initials."""
    import re
    name = name.lower().strip()
    name = re.sub(r'\b[a-z]\.\s*', '', name)  # Remove middle initials
    name = re.sub(r'\s+', ' ', name)
    return name


def _merge_into_existing(
    contacts: list[dict],
    new_contact: dict,
    key: str,
    value: str,
) -> None:
    """Merge data from new_contact into an existing contact in the list."""
    for existing in contacts:
        existing_val = (existing.get(key) or "").strip().lower().rstrip("/")
        if key == "full_name":
            existing_val = _normalize_name(existing.get("full_name", ""))

        if existing_val == value:
            # Fill in missing fields from new contact
            for field in ["email", "phone", "linkedin_url", "designation", "city"]:
                if not existing.get(field) and new_contact.get(field):
                    existing[field] = new_contact[field]
            # Take higher confidence
            existing["confidence"] = max(
                existing.get("confidence", 0),
                new_contact.get("confidence", 0),
            )
            # Note merged sources
            if new_contact.get("source") != existing.get("source"):
                existing["source"] = f"{existing.get('source', '')},{new_contact.get('source', '')}"
            break


def _merge_contacts(
    existing: list[dict],
    new_contacts: list[dict],
) -> list[dict]:
    """Merge new contacts into existing KB contacts, deduplicating."""
    combined = list(existing) + new_contacts
    return _deduplicate_contacts(combined)
