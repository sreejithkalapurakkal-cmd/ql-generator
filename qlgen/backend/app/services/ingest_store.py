"""Redis-backed store for pending ingest rows (upload → confirm handoff).

The ingest flow is multi-step: /upload (or /paste) parses a file and returns a
batch_id, then /confirm processes the stored rows. The rows must survive the
gap between those two requests across multiple uvicorn workers and ECS tasks,
so they cannot live in an in-process dict.

Reuses the Redis connection singleton from event_store and falls back to an
in-memory dict when Redis is unavailable (local development).
"""

import json
import logging
from typing import Optional

from app.services.event_store import get_redis

logger = logging.getLogger(__name__)

# Rows only need to live from upload until the user confirms the column mapping.
# 1 hour comfortably covers that flow while bounding stale memory in Redis.
INGEST_ROWS_TTL_SECONDS = 3600

# In-memory fallback for local development without Redis.
_fallback_rows: dict[str, list[dict]] = {}


def _rows_key(batch_id: str) -> str:
    return f"ingest:rows:{batch_id}"


async def set_pending_rows(batch_id: str, rows: list[dict]) -> None:
    """Store parsed rows for a batch, awaiting confirmation."""
    r = await get_redis()
    if r:
        # default=str guards against any non-JSON-native cell values; parse_xlsx
        # and parse_csv already stringify cells, so this is normally a no-op.
        await r.set(
            _rows_key(batch_id),
            json.dumps(rows, default=str),
            ex=INGEST_ROWS_TTL_SECONDS,
        )
    else:
        _fallback_rows[batch_id] = rows


async def pop_pending_rows(batch_id: str) -> Optional[list[dict]]:
    """Atomically fetch and remove the pending rows for a batch.

    Returns None if the batch's rows are absent (never stored or expired).
    """
    r = await get_redis()
    if r:
        raw = await r.getdel(_rows_key(batch_id))
        return json.loads(raw) if raw else None
    return _fallback_rows.pop(batch_id, None)
