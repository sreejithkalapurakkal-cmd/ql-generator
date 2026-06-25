"""Request observability middleware.

Adds structured logging, request tracing (request_id), and timing metrics
to all API requests. Provides a /health/metrics endpoint for basic
operational visibility.
"""
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("qlgen.requests")


# ──────────────────────────────────────────────────────────────────
# Metrics store (in-memory, reset on restart)
#
# Cardinality bounds prevent unbounded growth from dynamic labels
# (e.g. unique error strings, request paths with UUIDs).
# ──────────────────────────────────────────────────────────────────

_MAX_COUNTER_KEYS = 5000
_MAX_ENDPOINT_KEYS = 1000
_HISTOGRAM_WINDOW = 1000  # keep last N observations per series

_start_time = time.time()
_request_count = 0
_error_count = 0
_total_duration_ms = 0.0
_endpoint_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "errors": 0})

# Named counters: key = (name, frozenset(labels.items())) -> int
_counters: dict[tuple, int] = defaultdict(int)

# Named histograms: key = (name, frozenset(labels.items())) -> deque of observations
_histograms: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=_HISTOGRAM_WINDOW))


def _label_key(name: str, labels: dict | None) -> tuple:
    """Create a hashable key from metric name and optional labels."""
    label_set = frozenset((labels or {}).items())
    return (name, label_set)


def inc_counter(name: str, labels: dict = None, value: int = 1) -> None:
    """Increment a named counter.

    Args:
        name: Counter name (e.g. 'tool_calls_total').
        labels: Optional dict of label key/value pairs.
        value: Amount to increment (default 1).
    """
    key = _label_key(name, labels)
    if key not in _counters and len(_counters) >= _MAX_COUNTER_KEYS:
        return  # cardinality cap reached; drop to avoid unbounded growth
    _counters[key] += value


def observe_histogram(name: str, value: float, labels: dict = None) -> None:
    """Record a histogram observation.

    Args:
        name: Histogram name (e.g. 'tool_call_duration_ms').
        value: Observed value.
        labels: Optional dict of label key/value pairs.
    """
    key = _label_key(name, labels)
    if key not in _histograms and len(_histograms) >= _MAX_COUNTER_KEYS:
        return
    _histograms[key].append(value)


def log_tool_call(tool_name: str, duration_ms: float, success: bool, error: str = None) -> None:
    """Log a tool call by incrementing counters and recording duration.

    Args:
        tool_name: Name of the tool that was called.
        duration_ms: How long the call took in milliseconds.
        success: Whether the call succeeded.
        error: Optional error message if the call failed.
    """
    status = "success" if success else "error"
    labels = {"tool": tool_name, "status": status}

    inc_counter("tool_calls_total", labels)
    observe_histogram("tool_call_duration_ms", duration_ms, {"tool": tool_name})

    if not success and error:
        inc_counter("tool_call_errors_total", {"tool": tool_name, "error": error[:200]})

    logger.info(
        "Tool call: %s %s (%.1fms)%s",
        tool_name,
        status,
        duration_ms,
        f" error={error[:200]}" if error else "",
    )


def _summarize_histogram(observations: list[float]) -> dict:
    """Compute summary statistics for a list of observations."""
    if not observations:
        return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
    sorted_obs = sorted(observations)
    n = len(sorted_obs)
    return {
        "count": n,
        "sum": round(sum(sorted_obs), 2),
        "min": round(sorted_obs[0], 2),
        "max": round(sorted_obs[-1], 2),
        "avg": round(sum(sorted_obs) / n, 2),
        "p50": round(sorted_obs[int(n * 0.5)], 2),
        "p95": round(sorted_obs[min(int(n * 0.95), n - 1)], 2),
        "p99": round(sorted_obs[min(int(n * 0.99), n - 1)], 2),
    }


def get_metrics() -> dict:
    """Get current API metrics including named counters and histograms."""
    uptime = time.time() - _start_time
    avg_latency = _total_duration_ms / _request_count if _request_count > 0 else 0

    # Top 10 slowest endpoints
    top_slow = sorted(
        _endpoint_stats.items(),
        key=lambda x: x[1]["total_ms"] / max(x[1]["count"], 1),
        reverse=True,
    )[:10]

    # Serialize counters
    counters_out = {}
    for (name, label_set), value in _counters.items():
        labels = dict(label_set) if label_set else {}
        counters_out.setdefault(name, []).append({"labels": labels, "value": value})

    # Serialize histograms
    histograms_out = {}
    for (name, label_set), observations in _histograms.items():
        labels = dict(label_set) if label_set else {}
        histograms_out.setdefault(name, []).append({
            "labels": labels,
            **_summarize_histogram(observations),
        })

    return {
        "uptime_seconds": round(uptime, 1),
        "total_requests": _request_count,
        "total_errors": _error_count,
        "avg_latency_ms": round(avg_latency, 2),
        "requests_per_minute": round(_request_count / max(uptime / 60, 1), 1),
        "top_endpoints": [
            {
                "path": path,
                "count": stats["count"],
                "avg_ms": round(stats["total_ms"] / max(stats["count"], 1), 1),
                "errors": stats["errors"],
            }
            for path, stats in top_slow
        ],
        "counters": counters_out,
        "histograms": histograms_out,
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────────────────────────
# Structured JSON Formatter
# ──────────────────────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """JSON log formatter for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include extra fields
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "user_id"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


# ──────────────────────────────────────────────────────────────────
# Request Middleware
# ──────────────────────────────────────────────────────────────────

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Adds request_id header, timing, and structured request logging."""

    async def dispatch(self, request: Request, call_next) -> Response:
        global _request_count, _error_count, _total_duration_ms

        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Time the request
        start = time.time()

        try:
            response = await call_next(request)
        except Exception:
            _error_count += 1
            raise

        duration_ms = (time.time() - start) * 1000

        # Update metrics
        _request_count += 1
        _total_duration_ms += duration_ms
        path = request.url.path
        if path in _endpoint_stats or len(_endpoint_stats) < _MAX_ENDPOINT_KEYS:
            _endpoint_stats[path]["count"] += 1
            _endpoint_stats[path]["total_ms"] += duration_ms
        if response.status_code >= 400:
            _error_count += 1
            if path in _endpoint_stats:
                _endpoint_stats[path]["errors"] += 1

        # Add headers
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        # Log request (skip health checks and static assets)
        if not path.startswith("/health") and not path.startswith("/docs"):
            log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
            # Only log slow requests at INFO (>500ms) or all at DEBUG
            if duration_ms > 500 or response.status_code >= 400:
                logger.log(
                    log_level,
                    f"{request.method} {path} → {response.status_code} ({duration_ms:.0f}ms)",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 1),
                    },
                )

        return response


def setup_structured_logging(json_format: bool = False):
    """Configure structured logging for the application.

    Args:
        json_format: If True, use JSON formatter (for production/log aggregation).
                     If False, use standard formatter (for development).
    """
    if json_format:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logging.root.handlers = [handler]
        logging.root.setLevel(logging.INFO)
    else:
        # Standard format for dev
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
