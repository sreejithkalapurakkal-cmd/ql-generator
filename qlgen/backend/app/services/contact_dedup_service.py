"""Server-side contact deduplication.

Post-save dedup function that normalizes LinkedIn URLs, performs fuzzy
name matching, and exact email matching to merge duplicate contacts.
Recalculates confidence based on source count.
"""

import logging
import re
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact

logger = logging.getLogger(__name__)


def _normalize_linkedin_url(url: str | None) -> str:
    """Normalize LinkedIn URL: strip query params, trailing slash, lowercase."""
    if not url:
        return ""
    url = url.split("?")[0].rstrip("/").lower()
    # Ensure consistent format
    url = re.sub(r"https?://(?:www\.)?linkedin\.com", "https://linkedin.com", url)
    return url


def _normalize_name(name: str | None) -> str:
    """Normalize a contact name for comparison."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


async def deduplicate_company_contacts(
    db: AsyncSession,
    company_id: UUID,
) -> int:
    """Deduplicate contacts for a single company.

    Merges by: (1) exact normalized LinkedIn URL, (2) exact email,
    (3) fuzzy name match (>90% similarity within same company).

    Returns number of duplicates removed.
    """
    from rapidfuzz import fuzz

    result = await db.execute(
        select(Contact).where(Contact.company_id == company_id)
    )
    contacts = list(result.scalars().all())

    if len(contacts) <= 1:
        return 0

    # Group contacts by various keys for merging
    # Key priority: LinkedIn URL > Email > Fuzzy Name
    groups: list[list[Contact]] = []
    assigned: set[UUID] = set()

    # Pass 1: Group by normalized LinkedIn URL
    by_linkedin: dict[str, list[Contact]] = {}
    for c in contacts:
        li = _normalize_linkedin_url(c.linkedin_url)
        if li:
            by_linkedin.setdefault(li, []).append(c)

    for li_contacts in by_linkedin.values():
        if len(li_contacts) > 1:
            groups.append(li_contacts)
            for c in li_contacts:
                assigned.add(c.id)

    # Pass 2: Group by email (for unassigned contacts)
    by_email: dict[str, list[Contact]] = {}
    for c in contacts:
        if c.id in assigned:
            continue
        if c.email:
            email = c.email.lower().strip()
            by_email.setdefault(email, []).append(c)

    for email_contacts in by_email.values():
        if len(email_contacts) > 1:
            groups.append(email_contacts)
            for c in email_contacts:
                assigned.add(c.id)

    # Pass 3: Fuzzy name match (>90%) for remaining unassigned
    unassigned = [c for c in contacts if c.id not in assigned]
    name_groups: dict[int, list[Contact]] = {}
    group_id = 0

    for i, c1 in enumerate(unassigned):
        if c1.id in assigned:
            continue
        name1 = _normalize_name(c1.full_name)
        if not name1 or len(name1) < 4:
            continue

        current_group = [c1]
        assigned.add(c1.id)

        for c2 in unassigned[i + 1:]:
            if c2.id in assigned:
                continue
            name2 = _normalize_name(c2.full_name)
            if not name2 or len(name2) < 4:
                continue

            if fuzz.ratio(name1, name2) > 90:
                current_group.append(c2)
                assigned.add(c2.id)

        if len(current_group) > 1:
            groups.append(current_group)

    # Merge each group: keep the best contact, delete the rest
    duplicates_removed = 0
    for group in groups:
        if len(group) <= 1:
            continue

        # Score each contact by data richness
        def _richness(c: Contact) -> int:
            score = 0
            if c.email:
                score += 3
            if c.phone:
                score += 2
            if c.linkedin_url:
                score += 2
            if c.full_name:
                score += 1
            if c.designation:
                score += 1
            if c.confidence and c.confidence > 0.5:
                score += 1
            return score

        # Sort by richness (best first)
        group.sort(key=_richness, reverse=True)
        keeper = group[0]

        # Merge data from duplicates into the keeper
        for dup in group[1:]:
            if not keeper.email and dup.email:
                keeper.email = dup.email
            if not keeper.phone and dup.phone:
                keeper.phone = dup.phone
            if not keeper.linkedin_url and dup.linkedin_url:
                keeper.linkedin_url = dup.linkedin_url
            if not keeper.full_name and dup.full_name:
                keeper.full_name = dup.full_name
            if not keeper.first_name and dup.first_name:
                keeper.first_name = dup.first_name
            if not keeper.last_name and dup.last_name:
                keeper.last_name = dup.last_name
            if not keeper.designation and dup.designation:
                keeper.designation = dup.designation
            if not keeper.role_category and dup.role_category:
                keeper.role_category = dup.role_category

        # Recalculate confidence based on source count
        source_count = len(group)
        if source_count >= 3:
            keeper.confidence = 0.95
        elif source_count == 2:
            keeper.confidence = max(keeper.confidence or 0, 0.80)

        # Delete duplicates
        for dup in group[1:]:
            await db.delete(dup)
            duplicates_removed += 1

    if duplicates_removed > 0:
        await db.flush()
        logger.info(
            f"Contact dedup for company {company_id}: "
            f"removed {duplicates_removed} duplicates from {len(contacts)} contacts"
        )

    return duplicates_removed
