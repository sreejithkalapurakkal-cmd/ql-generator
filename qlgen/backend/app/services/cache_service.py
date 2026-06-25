"""TTL-based in-memory cache service.

Provides a simple cache layer for frequently-accessed computed data
(dashboard stats, signal feed counts, company KB lookups) and
per-tool result caching with tool-specific TTLs.

Automatically evicts entries after their TTL expires.
Thread-safe via dict operations (GIL-protected in CPython).
"""
import hashlib
import json
import logging
import time
from typing import Any, Callable, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")

# In-memory cache: key → (value, expires_at)
_cache: dict[str, tuple[Any, float]] = {}

# Default TTL values (seconds)
DEFAULT_TTL = 60
CACHE_TTLS = {
    "dashboard_stats": 60,
    "signal_feed_count": 30,
    "company_kb": 300,
    "signal_rules": 120,
    "notification_count": 15,
}


def cache_get(key: str) -> Any | None:
    """Get a cached value if it exists and hasn't expired."""
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return value


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    """Set a cached value with TTL in seconds."""
    if ttl is None:
        ttl = DEFAULT_TTL
    _cache[key] = (value, time.time() + ttl)


def cache_delete(key: str) -> None:
    """Delete a cached entry."""
    _cache.pop(key, None)


def cache_delete_prefix(prefix: str) -> int:
    """Delete all entries matching a prefix. Returns count deleted."""
    keys_to_delete = [k for k in _cache if k.startswith(prefix)]
    for k in keys_to_delete:
        _cache.pop(k, None)
    return len(keys_to_delete)


def cache_clear() -> int:
    """Clear entire cache. Returns count of entries cleared."""
    count = len(_cache)
    _cache.clear()
    return count


def cache_stats() -> dict:
    """Get cache statistics."""
    now = time.time()
    total = len(_cache)
    expired = sum(1 for _, (_, exp) in _cache.items() if now > exp)
    return {
        "total_entries": total,
        "expired_entries": expired,
        "active_entries": total - expired,
    }


def cached(key_prefix: str, ttl: int | None = None):
    """Decorator for caching async function results.

    Usage:
        @cached("dashboard_stats", ttl=60)
        async def get_dashboard_stats(db, user_id):
            ...

    The cache key is f"{key_prefix}:{args[1]}" (assumes arg[1] is the unique ID).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from prefix + first non-db arg
            cache_key_parts = [key_prefix]
            for arg in args[1:]:  # skip db session
                cache_key_parts.append(str(arg))
            for v in kwargs.values():
                if v is not None:
                    cache_key_parts.append(str(v))
            cache_key = ":".join(cache_key_parts)

            # Check cache
            result = cache_get(cache_key)
            if result is not None:
                return result

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            effective_ttl = ttl or CACHE_TTLS.get(key_prefix, DEFAULT_TTL)
            cache_set(cache_key, result, effective_ttl)

            return result
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────────
# Per-tool caching
# ──────────────────────────────────────────────────────────────────

TOOL_CACHE_TTLS = {
    "apollo": 43200,          # 12h — contact data changes slowly
    "linkedin_search": 21600, # 6h
    "tavily": 14400,          # 4h — news changes frequently
    "exa": 14400,             # 4h
    "news_sentiment": 7200,   # 2h — time-sensitive
    "web_scraper": 3600,      # 1h
    "sec": 604800,            # 7d — SEC filings are permanent
    "find_executives": 86400, # 24h — leadership changes rarely
    "google_places": 604800,  # 7d — locations change slowly
    "simfin": 86400,          # 24h
    "fmp": 86400,             # 24h
    "duckduckgo": 7200,       # 2h
}


def _hash_tool_args(*args, **kwargs) -> str:
    """Create a stable hash of tool call arguments for cache keying."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def tool_cache_get(tool_name: str, *args, **kwargs) -> Any | None:
    """Check if a tool call result is cached."""
    args_hash = _hash_tool_args(*args, **kwargs)
    cache_key = f"tool:{tool_name}:{args_hash}"
    return cache_get(cache_key)


def tool_cache_set(tool_name: str, result: Any, *args, **kwargs) -> None:
    """Cache a tool call result with the tool-specific TTL."""
    args_hash = _hash_tool_args(*args, **kwargs)
    cache_key = f"tool:{tool_name}:{args_hash}"
    ttl = TOOL_CACHE_TTLS.get(tool_name, DEFAULT_TTL)
    cache_set(cache_key, result, ttl)


def tool_cached(tool_name: str):
    """Decorator for caching tool call results with per-tool TTLs.

    Usage:
        @tool_cached("apollo")
        def search_apollo(company_name: str, domain: str) -> dict:
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = tool_cache_get(tool_name, *args, **kwargs)
            if result is not None:
                logger.debug(f"Tool cache hit: {tool_name}")
                return result
            result = func(*args, **kwargs)
            if result is not None:
                tool_cache_set(tool_name, result, *args, **kwargs)
            return result
        return wrapper
    return decorator


def invalidate_tool_cache(tool_name: str | None = None) -> int:
    """Invalidate cached tool results. If tool_name is None, clear all tool caches."""
    prefix = f"tool:{tool_name}:" if tool_name else "tool:"
    return cache_delete_prefix(prefix)


def invalidate_user_cache(user_id: str) -> int:
    """Invalidate all cached data for a user."""
    return cache_delete_prefix(f"dashboard_stats:{user_id}") + \
           cache_delete_prefix(f"signal_feed_count:{user_id}")
