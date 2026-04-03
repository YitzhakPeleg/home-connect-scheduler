from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from home_connect_scheduler.settings import settings
from home_connect_scheduler.store import load
from home_connect_scheduler.web_deps import templates

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    data = load()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "connected": data.tokens is not None,
            "selected_appliance": data.selected_appliance,
            "use_simulator": settings.use_simulator,
            "redirect_uri": settings.redirect_uri,
            "api_base_url": settings.api_base_url,
        },
    )
