"""Request observability middleware.

Adds structured logging, request tracing (request_id), and timing metrics
to all API requests. Provides a /health/metrics endpoint for basic
operational visibility.
"""
import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("qlgen.requests")


# ──────────────────────────────────────────────────────────────────
# Metrics store (in-memory, reset on restart)
# ──────────────────────────────────────────────────────────────────

_start_time = time.time()
_request_count = 0
_error_count = 0
_total_duration_ms = 0.0
_endpoint_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "errors": 0})


def get_metrics() -> dict:
    """Get current API metrics."""
    uptime = time.time() - _start_time
    avg_latency = _total_duration_ms / _request_count if _request_count > 0 else 0

    # Top 10 slowest endpoints
    top_slow = sorted(
        _endpoint_stats.items(),
        key=lambda x: x[1]["total_ms"] / max(x[1]["count"], 1),
        reverse=True,
    )[:10]

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
        _endpoint_stats[path]["count"] += 1
        _endpoint_stats[path]["total_ms"] += duration_ms
        if response.status_code >= 400:
            _error_count += 1
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
