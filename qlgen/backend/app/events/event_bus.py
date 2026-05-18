"""In-process async event bus for service decoupling.

Allows services to emit events that other services can subscribe to,
without direct imports or coupling. Handlers run asynchronously.

Usage:
    from app.events.event_bus import bus

    # Register handler
    @bus.on("signal.detected")
    async def handle_signal(payload):
        await recompute_heat(payload["company_kb_id"])

    # Emit event
    await bus.emit("signal.detected", {"company_kb_id": "...", "signal_id": "..."})
"""
import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    """In-process async event bus."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._emit_count: int = 0
        self._error_count: int = 0

    def on(self, event_type: str, handler: EventHandler | None = None):
        """Register a handler for an event type. Can be used as a decorator."""
        if handler is not None:
            self._handlers[event_type].append(handler)
            return handler

        def decorator(fn: EventHandler) -> EventHandler:
            self._handlers[event_type].append(fn)
            return fn
        return decorator

    def off(self, event_type: str, handler: EventHandler):
        """Remove a handler."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None):
        """Emit an event to all registered handlers. Handlers run concurrently."""
        self._emit_count += 1
        payload = payload or {}
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            return

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_call(event_type, handler, payload))

        await asyncio.gather(*tasks)

    async def _safe_call(self, event_type: str, handler: EventHandler, payload: dict):
        """Call handler with error isolation — one failing handler doesn't break others."""
        try:
            await handler(payload)
        except Exception as e:
            self._error_count += 1
            logger.error(
                f"EventBus handler error for '{event_type}': {e}",
                exc_info=True,
            )

    def stats(self) -> dict:
        """Get event bus statistics."""
        return {
            "registered_events": len(self._handlers),
            "total_handlers": sum(len(h) for h in self._handlers.values()),
            "total_emits": self._emit_count,
            "total_errors": self._error_count,
            "events": {k: len(v) for k, v in self._handlers.items()},
        }


# Singleton instance
bus = EventBus()


# ──────────────────────────────────────────────────────────────────
# Standard event types
# ──────────────────────────────────────────────────────────────────

class Events:
    """Standard event type constants."""
    SIGNAL_DETECTED = "signal.detected"
    SIGNAL_DISMISSED = "signal.dismissed"
    SIGNAL_SAVED = "signal.saved"
    SIGNAL_ACTED_ON = "signal.acted_on"
    BRIEF_GENERATED = "brief.generated"
    BRIEF_REGENERATED = "brief.regenerated"
    DRAFT_CREATED = "draft.created"
    DRAFT_SENT = "draft.sent"
    CONTACT_ENRICHED = "contact.enriched"
    RESEARCH_STARTED = "research.started"
    RESEARCH_COMPLETED = "research.completed"
    RESEARCH_FAILED = "research.failed"
    SOURCE_CRAWLED = "source.crawled"
    SOURCE_CHANGED = "source.changed"
    MONITORING_COMPLETED = "monitoring.completed"
    CORRELATION_FOUND = "correlation.found"
