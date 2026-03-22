"""Redis-backed event store for pipeline SSE events and cancellation state.

Replaces the in-memory pipeline_events dict and cancelled_runs set so that
events are shared across multiple uvicorn workers and ECS tasks.

Falls back to in-memory storage if Redis is unavailable (development mode).
"""

import json
import logging
import threading
from typing import Optional

import redis as sync_redis
import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

# TTL for pipeline event keys (2 hours — covers long-running pipelines + buffer)
EVENT_TTL_SECONDS = 7200

_redis_client: Optional[aioredis.Redis] = None
_sync_redis_client: Optional[sync_redis.Redis] = None
_sync_lock = threading.Lock()
_use_fallback = False

# In-memory fallback for local development without Redis
_fallback_events: dict[str, list] = {}
_fallback_cancelled: set[str] = set()


async def get_redis() -> Optional[aioredis.Redis]:
    """Get or create the async Redis client singleton."""
    global _redis_client, _use_fallback

    if _use_fallback:
        return None

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()
    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        await _redis_client.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL)
        return _redis_client
    except Exception as e:
        logger.warning("Redis unavailable (%s), falling back to in-memory event store", e)
        _redis_client = None
        _use_fallback = True
        return None


def _get_sync_redis() -> Optional[sync_redis.Redis]:
    """Get or create a sync Redis client for use in thread-pool callbacks."""
    global _sync_redis_client, _use_fallback

    if _use_fallback:
        return None

    if _sync_redis_client is not None:
        return _sync_redis_client

    with _sync_lock:
        if _sync_redis_client is not None:
            return _sync_redis_client
        settings = get_settings()
        try:
            _sync_redis_client = sync_redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            _sync_redis_client.ping()
            return _sync_redis_client
        except Exception as e:
            logger.warning("Sync Redis unavailable (%s), using in-memory fallback", e)
            _use_fallback = True
            return None


def _events_key(run_id: str) -> str:
    return f"pipeline:{run_id}:events"


def _cancelled_key() -> str:
    return "pipeline:cancelled"


async def init_run(run_id: str) -> None:
    """Initialize event storage for a new pipeline run."""
    r = await get_redis()
    if r:
        key = _events_key(run_id)
        # Delete any stale events from a previous run with the same ID
        await r.delete(key)
        # Set a placeholder so the key exists; will be removed on first real push
        await r.expire(key, EVENT_TTL_SECONDS)
    else:
        _fallback_events[run_id] = []


async def push_event(run_id: str, event: dict) -> None:
    """Append an SSE event to the store for a given run."""
    r = await get_redis()
    if r:
        key = _events_key(run_id)
        await r.rpush(key, json.dumps(event))
        await r.expire(key, EVENT_TTL_SECONDS)
    else:
        if run_id in _fallback_events:
            _fallback_events[run_id].append(event)


async def get_events(run_id: str, start_index: int = 0) -> list[dict]:
    """Retrieve events from start_index onward. Returns a list of event dicts."""
    r = await get_redis()
    if r:
        key = _events_key(run_id)
        raw = await r.lrange(key, start_index, -1)
        return [json.loads(item) for item in raw]
    else:
        events = _fallback_events.get(run_id, [])
        return events[start_index:]


async def get_event_count(run_id: str) -> int:
    """Return the total number of events for a run."""
    r = await get_redis()
    if r:
        return await r.llen(_events_key(run_id))
    else:
        return len(_fallback_events.get(run_id, []))


async def mark_cancelled(run_id: str) -> None:
    """Mark a pipeline run as cancelled."""
    r = await get_redis()
    if r:
        await r.sadd(_cancelled_key(), run_id)
        # Auto-expire cancelled entries after 1 hour
        await r.expire(_cancelled_key(), 3600)
    else:
        _fallback_cancelled.add(run_id)


async def is_cancelled(run_id: str) -> bool:
    """Check if a pipeline run has been cancelled."""
    r = await get_redis()
    if r:
        return await r.sismember(_cancelled_key(), run_id)
    else:
        return run_id in _fallback_cancelled


async def clear_cancelled(run_id: str) -> None:
    """Remove a run from the cancelled set."""
    r = await get_redis()
    if r:
        await r.srem(_cancelled_key(), run_id)
    else:
        _fallback_cancelled.discard(run_id)


async def cleanup_run(run_id: str) -> None:
    """Clean up event data for a completed/deleted run."""
    r = await get_redis()
    if r:
        await r.delete(_events_key(run_id))
        await r.srem(_cancelled_key(), run_id)
    else:
        _fallback_events.pop(run_id, None)
        _fallback_cancelled.discard(run_id)


# ──────────────────────────────────────────────────────────────────
# Sync variants for use in thread-pool callbacks (lead_gen_agent.py)
# ──────────────────────────────────────────────────────────────────

def push_event_sync(run_id: str, event: dict) -> None:
    """Synchronous version of push_event for use in agent callback threads."""
    r = _get_sync_redis()
    if r:
        try:
            key = _events_key(run_id)
            r.rpush(key, json.dumps(event))
            r.expire(key, EVENT_TTL_SECONDS)
        except Exception:
            pass  # Non-fatal: SSE event may be missed but pipeline continues
    else:
        if run_id in _fallback_events:
            _fallback_events[run_id].append(event)


def is_cancelled_sync(run_id: str) -> bool:
    """Synchronous version of is_cancelled for use in agent callback threads."""
    r = _get_sync_redis()
    if r:
        try:
            return r.sismember(_cancelled_key(), run_id)
        except Exception:
            return False
    else:
        return run_id in _fallback_cancelled
