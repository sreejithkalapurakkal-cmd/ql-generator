"""Centralized DuckDuckGo rate limiter.

All DDG-using tools call through this single gateway so that rate-limit
state is shared across the entire process. Uses a token-bucket algorithm:
1 token replenished every 5 seconds, burst capacity of 3.

When any caller hits a rate limit, ALL callers are instantly aware and
stop sending requests for a cooldown period.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Import RatelimitException at module level so it's always available
# in except clauses. If the ddgs package is missing or restructured,
# fall back gracefully.
try:
    from ddgs.exceptions import RatelimitException as _DDGRatelimitException
except (ImportError, ModuleNotFoundError, AttributeError):
    _DDGRatelimitException = None


class DDGRateLimiter:
    """Process-wide singleton rate limiter for DuckDuckGo searches."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._bucket_lock = threading.Lock()
        # Token bucket parameters
        self._tokens = 3.0
        self._max_tokens = 3.0
        self._refill_rate = 1.0 / 5.0  # 1 token per 5 seconds
        self._last_refill = time.monotonic()
        # Global rate-limit state
        self._rate_limited = False
        self._rate_limit_until = 0.0
        self._cooldown_seconds = 60.0  # Wait 60s after a rate limit hit
        # Stats
        self._total_requests = 0
        self._total_rate_limits = 0

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def _is_in_cooldown(self) -> bool:
        if not self._rate_limited:
            return False
        if time.monotonic() >= self._rate_limit_until:
            self._rate_limited = False
            logger.info("DDG rate-limit cooldown expired, resuming requests")
            return False
        return True

    def mark_rate_limited(self):
        """Called when any DDG request gets rate-limited."""
        with self._bucket_lock:
            self._rate_limited = True
            self._rate_limit_until = time.monotonic() + self._cooldown_seconds
            self._tokens = 0.0
            self._total_rate_limits += 1
            logger.warning(
                f"DDG rate limit hit (#{self._total_rate_limits}). "
                f"Cooling down for {self._cooldown_seconds}s. "
                f"All DDG requests paused."
            )

    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire a token to make a DDG request.

        Returns True if a token was acquired, False if rate-limited or timed out.
        Blocks until a token is available or timeout is reached.
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            with self._bucket_lock:
                if self._is_in_cooldown():
                    remaining = self._rate_limit_until - time.monotonic()
                    logger.debug(f"DDG in cooldown, {remaining:.0f}s remaining")
                    # Don't wait the full cooldown in the lock
                    wait_time = min(remaining, 2.0)
                else:
                    self._refill()
                    if self._tokens >= 1.0:
                        self._tokens -= 1.0
                        self._total_requests += 1
                        return True
                    # Calculate wait time until next token
                    wait_time = (1.0 - self._tokens) / self._refill_rate

            time.sleep(min(wait_time, 2.0))

        logger.warning("DDG rate limiter: acquire timed out")
        return False

    @property
    def is_rate_limited(self) -> bool:
        with self._bucket_lock:
            return self._is_in_cooldown()

    @property
    def stats(self) -> dict:
        with self._bucket_lock:
            return {
                "total_requests": self._total_requests,
                "total_rate_limits": self._total_rate_limits,
                "tokens_available": round(self._tokens, 2),
                "is_rate_limited": self._rate_limited,
            }


# Module-level singleton
_limiter = DDGRateLimiter()


def ddg_search(query: str, max_results: int = 10) -> list[dict]:
    """Execute a DuckDuckGo search through the centralized rate limiter.

    All tools should call this instead of using DDGS directly.

    Returns:
        list of result dicts, or a single-element list with an error dict
        if rate-limited or failed.
    """
    if _limiter.is_rate_limited:
        return [{
            "error": (
                "RATE_LIMITED: DuckDuckGo is in cooldown across all tools. "
                "Do NOT retry. Switch to exa_search, tavily_search, or "
                "apollo_company_search instead."
            ),
            "rate_limited": True,
        }]

    if not _limiter.acquire(timeout=30.0):
        return [{
            "error": (
                "RATE_LIMITED: DuckDuckGo rate limiter timed out. "
                "Switch to other search tools."
            ),
            "rate_limited": True,
        }]

    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=min(max_results, 10)))
        return results

    except Exception as e:
        # Check if this is a DDG rate-limit exception
        if _DDGRatelimitException and isinstance(e, _DDGRatelimitException):
            _limiter.mark_rate_limited()
            return [{
                "error": (
                    "RATE_LIMITED: DuckDuckGo is blocking automated queries. "
                    "Do NOT retry this tool. Switch to exa_search, tavily_search, or "
                    "apollo_company_search instead."
                ),
                "rate_limited": True,
            }]
        if "ratelimit" in str(e).lower():
            _limiter.mark_rate_limited()
            return [{
                "error": f"RATE_LIMITED: {e}. Switch to other search tools.",
                "rate_limited": True,
            }]
        return [{"error": str(e)}]


def is_rate_limited() -> bool:
    """Check if DDG is currently in cooldown."""
    return _limiter.is_rate_limited


def get_stats() -> dict:
    """Get rate limiter statistics."""
    return _limiter.stats
