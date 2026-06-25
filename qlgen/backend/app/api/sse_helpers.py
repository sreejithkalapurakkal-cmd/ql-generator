"""Shared SSE streaming helpers for async agent operations.

Provides a standard event_generator factory and StreamingResponse builder
so that all /stream endpoints share the same polling, keepalive, and
timeout logic.
"""
import asyncio
import json
from typing import Set

from fastapi.responses import StreamingResponse

from app.services.event_store import get_events


def create_sse_stream(
    run_id: str,
    terminal_events: Set[str],
    timeout_cycles: int = 900,
    poll_interval: float = 0.2,
    keepalive_every: int = 25,
) -> StreamingResponse:
    """Create a standard SSE StreamingResponse for a background task.

    Args:
        run_id: The event store key (usually a UUID string).
        terminal_events: Set of event type strings that signal end of stream.
        timeout_cycles: Max polling cycles with no events before timeout (~timeout_cycles * poll_interval seconds).
        poll_interval: Seconds between polls.
        keepalive_every: Send keepalive comment every N empty cycles.
    """

    async def event_generator():
        last_index = 0
        no_event_cycles = 0

        while True:
            events = await get_events(run_id, last_index)
            if events:
                no_event_cycles = 0
                for evt in events:
                    event_type = evt.get("type", "progress")
                    data = json.dumps(evt.get("data", {}))
                    yield f"event: {event_type}\ndata: {data}\n\n"
                    last_index += 1
                    if event_type in terminal_events:
                        return
            else:
                no_event_cycles += 1
                if no_event_cycles > timeout_cycles:
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Stream timeout'})}\n\n"
                    return
                if no_event_cycles % keepalive_every == 0:
                    yield ": keepalive\n\n"

            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
