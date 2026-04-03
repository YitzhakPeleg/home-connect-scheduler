from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from home_connect_scheduler.routes import (
    appliances,
    auth,
    dashboard,
    events,
    history,
    schedules,
    settings,
)
from home_connect_scheduler.store import load
from home_connect_scheduler.web_deps import STATIC_DIR, templates


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from home_connect_scheduler.web_scheduler import start_web_scheduler, stop_web_scheduler

    start_web_scheduler()
    logger.info("Web scheduler started")
    yield
    stop_web_scheduler()
    logger.info("Web scheduler stopped")


app = FastAPI(title="Home Connect Scheduler", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(appliances.router)
app.include_router(schedules.router)
app.include_router(history.router)
app.include_router(settings.router)
app.include_router(events.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    data = load()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "connected": data.tokens is not None,
            "selected_appliance": data.selected_appliance,
            "schedules": data.schedules,
            "run_log": data.run_log[-10:],
        },
    )


def main() -> None:
    uvicorn.run(
        "home_connect_scheduler.webapp:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
