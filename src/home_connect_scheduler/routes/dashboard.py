from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.settings import settings
from home_connect_scheduler.store import load
from home_connect_scheduler.web_deps import templates

router = APIRouter(tags=["dashboard"])


@router.get("/api/status", response_class=HTMLResponse)
async def api_status(request: Request) -> HTMLResponse:
    data = load()
    if not data.selected_appliance or not data.tokens:
        return HTMLResponse("<p>No appliance selected or not connected.</p>")

    client = HomeConnectClient()
    try:
        status_items = await client.get_status(data.selected_appliance)

        # Try to get active program (404 when no program is running — that's fine)
        active_program: dict[str, Any] | None = None
        try:
            resp = await client._request(
                "GET",
                f"{settings.api_base_url}/api/homeappliances/{data.selected_appliance}/programs/active",
            )
            active_program = resp.json().get("data")
        except Exception:
            pass
    except Exception as exc:
        logger.error("Failed to fetch appliance status: {}", exc)
        return HTMLResponse(f"<p>Failed to fetch appliance status: {exc}</p>")
    finally:
        await client.close()

    return templates.TemplateResponse(
        request,
        "fragments/status_card.html",
        {
            "status_items": status_items,
            "active_program": active_program,
        },
    )
