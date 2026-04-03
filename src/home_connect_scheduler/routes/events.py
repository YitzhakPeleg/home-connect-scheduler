from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.store import load

router = APIRouter(prefix="/api", tags=["events"])


async def _event_stream(request: Request, ha_id: str) -> AsyncIterator[str]:
    """Proxy SSE events from Home Connect, rendering HTML fragments."""
    client = HomeConnectClient()
    try:
        async for event in client.stream_events(ha_id):
            if await request.is_disconnected():
                break

            event_type = event.get("event", "")
            data = event.get("data", "")

            # Forward raw event data as SSE
            if event_type == "KEEP-ALIVE":
                yield ": keepalive\n\n"
                continue

            # Parse the JSON data and render as HTML fragment
            try:
                items = json.loads(data) if data else {}
            except json.JSONDecodeError:
                items = {}

            yield f"event: {event_type}\ndata: {json.dumps(items)}\n\n"
    except Exception as exc:
        logger.error("SSE stream error: {}", exc)
    finally:
        await client.close()


@router.get("/events", response_model=None)
async def events(request: Request) -> StreamingResponse | HTMLResponse:
    data = load()
    if not data.selected_appliance or not data.tokens:
        return HTMLResponse("Not connected", status_code=400)

    return StreamingResponse(
        _event_stream(request, data.selected_appliance),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
