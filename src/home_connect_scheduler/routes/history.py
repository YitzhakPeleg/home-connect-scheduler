from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from home_connect_scheduler.store import load
from home_connect_scheduler.web_deps import templates

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_class=HTMLResponse)
async def run_history(request: Request) -> HTMLResponse:
    data = load()
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "connected": data.tokens is not None,
            "run_log": list(reversed(data.run_log)),
        },
    )
