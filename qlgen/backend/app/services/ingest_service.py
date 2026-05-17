"""Ingest service for company list uploads.

Handles XLSX/CSV/paste parsing, column auto-detection, KB-first
enrichment, and batch processing with progress events.
"""
import csv
import io
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest_batch import IngestBatch
from app.models.company_knowledge_base import CompanyKnowledgeBase
from app.services.company_kb_service import normalize_domain, lookup_from_kb
from app.services.event_store import push_event

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Column auto-detection
# ──────────────────────────────────────────────────────────────────

# Maps common column names to qlGen fields
COLUMN_ALIASES: dict[str, list[str]] = {
    "company_name": [
        "company name", "company", "name", "organization", "org name",
        "account name", "account", "business name", "firm",
    ],
    "domain": [
        "domain", "website", "url", "web", "company url", "company website",
        "company domain", "site", "homepage",
    ],
    "industry": [
        "industry", "sector", "vertical", "industry type", "business type",
    ],
    "country": [
        "country", "location", "geo", "geography", "region", "country/region",
        "hq country", "headquarters country",
    ],
    "city": [
        "city", "hq city", "headquarters city",
    ],
    "employee_count": [
        "employees", "employee count", "# employees", "headcount",
        "company size", "size", "num employees", "number of employees",
    ],
    "revenue": [
        "revenue", "annual revenue", "revenue estimate", "arr",
        "annual revenue estimate", "revenue range",
    ],
    "contact_name": [
        "contact name", "contact", "person", "full name", "first name",
        "lead name", "contact person",
    ],
    "contact_email": [
        "email", "contact email", "email address", "work email",
    ],
    "contact_title": [
        "title", "job title", "designation", "role", "position",
    ],
    "linkedin_url": [
        "linkedin", "linkedin url", "linkedin profile", "li url",
    ],
}


def auto_map_columns(headers: list[str]) -> dict[str, str]:
    """Heuristically map uploaded column names to qlGen fields.

    Returns: {source_column_name: target_field} for matched columns.
    """
    mapping: dict[str, str] = {}
    headers_lower = {h: h.lower().strip() for h in headers}

    for target_field, aliases in COLUMN_ALIASES.items():
        for header, h_lower in headers_lower.items():
            if header in mapping:
                continue
            if h_lower in aliases or any(alias in h_lower for alias in aliases):
                mapping[header] = target_field
                break

    return mapping


# ──────────────────────────────────────────────────────────────────
# File parsing
# ──────────────────────────────────────────────────────────────────

def parse_xlsx(file_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse XLSX file, return (headers, rows as dicts)."""
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return [], []

    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if not header_row:
        return [], []

    headers = [str(h).strip() if h else f"Column_{i}" for i, h in enumerate(header_row)]

    rows = []
    for row in rows_iter:
        row_dict = {}
        for i, val in enumerate(row):
            if i < len(headers) and val is not None:
                row_dict[headers[i]] = str(val).strip()
        if any(row_dict.values()):
            rows.append(row_dict)

    wb.close()
    return headers, rows


def parse_csv(file_bytes: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV file, return (headers, rows as dicts)."""
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = []
    for row in reader:
        cleaned = {k: (v or "").strip() for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return list(headers), rows


def parse_paste(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse pasted text (one company per line or comma-separated).

    Supports:
    - One company name/domain per line
    - Comma-separated on a single line
    - Mix of both
    """
    lines = text.strip().split("\n")
    entries = []
    for line in lines:
        # Split by comma if the line has commas
        parts = [p.strip() for p in line.split(",")]
        entries.extend(p for p in parts if p)

    # Classify each entry as a domain or company name
    rows = []
    for entry in entries:
        if _looks_like_domain(entry):
            rows.append({"domain": entry, "company_name": ""})
        else:
            rows.append({"company_name": entry, "domain": ""})

    headers = ["company_name", "domain"]
    return headers, rows


def _looks_like_domain(text: str) -> bool:
    """Check if text looks like a domain/URL."""
    text = text.lower().strip()
    if text.startswith(("http://", "https://")):
        return True
    return bool(re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?\.[a-z]{2,}$", text))


# ──────────────────────────────────────────────────────────────────
# Batch creation
# ──────────────────────────────────────────────────────────────────

async def create_ingest_batch(
    db: AsyncSession,
    user_id: UUID,
    name: str | None,
    filename: str | None,
    file_type: str,
    headers: list[str],
    row_count: int,
    column_mapping: dict[str, str],
    target_tracking_list_id: UUID | None = None,
) -> IngestBatch:
    """Create a new IngestBatch record."""
    batch = IngestBatch(
        user_id=user_id,
        name=name or filename or "Uploaded list",
        filename=filename,
        file_type=file_type,
        column_mapping=column_mapping,
        total_rows=row_count,
        target_tracking_list_id=target_tracking_list_id,
    )
    db.add(batch)
    await db.flush()
    return batch


# ──────────────────────────────────────────────────────────────────
# Batch processing (KB-first enrichment)
# ──────────────────────────────────────────────────────────────────

async def process_ingest_batch(
    db: AsyncSession,
    batch_id: UUID,
    rows: list[dict[str, str]],
    column_mapping: dict[str, str],
) -> IngestBatch:
    """Process an ingest batch: match against KB, create stubs for unknowns.

    Emits SSE progress events using the event store.

    Returns the list of (company_kb_id, is_new) tuples.
    """
    result = await db.execute(
        select(IngestBatch).where(IngestBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    batch.status = "processing"
    await db.flush()

    # Invert mapping: target_field -> source_column
    field_to_col: dict[str, str] = {v: k for k, v in column_mapping.items()}

    processed = 0
    matched_kb = 0
    newly_created = 0
    errors: list[dict] = []
    company_kb_ids: list[UUID] = []

    batch_id_str = str(batch_id)
    total = len(rows)

    for i, row in enumerate(rows):
        try:
            # Extract fields using column mapping
            company_name = row.get(field_to_col.get("company_name", ""), "").strip()
            domain = row.get(field_to_col.get("domain", ""), "").strip()
            industry = row.get(field_to_col.get("industry", ""), "").strip()
            country = row.get(field_to_col.get("country", ""), "").strip()
            city = row.get(field_to_col.get("city", ""), "").strip()

            emp_str = row.get(field_to_col.get("employee_count", ""), "").strip()
            employee_count = _parse_int(emp_str)

            rev_str = row.get(field_to_col.get("revenue", ""), "").strip()
            revenue = _parse_int(rev_str)

            if not company_name and not domain:
                errors.append({"row": i + 1, "error": "No company name or domain"})
                continue

            # Try KB lookup by domain first
            kb_record = None
            if domain:
                kb_record = await lookup_from_kb(domain, db)

            if kb_record:
                matched_kb += 1
                company_kb_ids.append(kb_record.id)
            else:
                # Create a new KB stub
                norm_domain = normalize_domain(domain) if domain else ""
                if not norm_domain and company_name:
                    # Use company name as a pseudo-domain for now
                    norm_domain = re.sub(r"[^a-z0-9]", "", company_name.lower())[:50]

                # Check if this pseudo-domain already exists
                if norm_domain:
                    existing = await db.execute(
                        select(CompanyKnowledgeBase).where(
                            CompanyKnowledgeBase.normalized_domain == norm_domain
                        )
                    )
                    kb_record = existing.scalar_one_or_none()

                if kb_record:
                    matched_kb += 1
                    company_kb_ids.append(kb_record.id)
                else:
                    # Create new KB record
                    kb_record = CompanyKnowledgeBase(
                        normalized_domain=norm_domain or f"unknown_{i}_{batch_id_str[:8]}",
                        canonical_name=company_name or domain,
                        industry=industry or None,
                        country=country or None,
                        city=city or None,
                        employee_count=employee_count,
                        revenue_estimate=revenue,
                        times_discovered=1,
                        first_discovered_at=datetime.now(timezone.utc),
                        data_sources={"source": "ingest", "batch_id": batch_id_str},
                    )
                    db.add(kb_record)
                    await db.flush()
                    newly_created += 1
                    company_kb_ids.append(kb_record.id)

            processed += 1

            # Emit progress every 10 rows or on last row
            if (i + 1) % 10 == 0 or i == total - 1:
                await push_event(batch_id_str, {
                    "type": "ingest_progress",
                    "data": {
                        "processed": processed,
                        "total": total,
                        "matched_kb": matched_kb,
                        "newly_created": newly_created,
                        "errors": len(errors),
                        "percent": round((i + 1) / total * 100),
                    },
                })

        except Exception as e:
            logger.warning(f"Ingest row {i+1} error: {e}")
            errors.append({"row": i + 1, "error": str(e)})

    # Update batch record
    batch.processed_rows = processed
    batch.matched_kb = matched_kb
    batch.newly_created = newly_created
    batch.errors = errors
    batch.status = "completed"

    await db.flush()

    # Emit completion event
    await push_event(batch_id_str, {
        "type": "ingest_completed",
        "data": {
            "batch_id": batch_id_str,
            "processed": processed,
            "matched_kb": matched_kb,
            "newly_created": newly_created,
            "errors": len(errors),
            "company_kb_ids": [str(kid) for kid in company_kb_ids],
        },
    })

    return batch


def _parse_int(s: str) -> int | None:
    """Parse a string to int, handling common formats."""
    if not s:
        return None
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[$,\s]", "", s)
    # Handle suffixes like "10M", "1.5B", "500K"
    match = re.match(r"^(\d+\.?\d*)\s*([KkMmBb])?$", cleaned)
    if match:
        num = float(match.group(1))
        suffix = (match.group(2) or "").upper()
        if suffix == "K":
            return int(num * 1_000)
        elif suffix == "M":
            return int(num * 1_000_000)
        elif suffix == "B":
            return int(num * 1_000_000_000)
        return int(num)
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None
