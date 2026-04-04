from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.models import DayOfWeek, Schedule
from home_connect_scheduler.store import load, save
from home_connect_scheduler.web_deps import templates
from home_connect_scheduler.web_scheduler import reload_jobs

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_class=HTMLResponse)
async def list_schedules(request: Request) -> HTMLResponse:
    data = load()
    programs: list[dict] = []
    if data.tokens and data.selected_appliance:
        client = HomeConnectClient()
        try:
            programs = await client.list_programs(data.selected_appliance)
        except Exception:
            pass
        finally:
            await client.close()

    return templates.TemplateResponse(
        request,
        "schedules.html",
        {
            "connected": data.tokens is not None,
            "schedules": data.schedules,
            "programs": programs,
            "days": list(DayOfWeek),
        },
    )


@router.post("", response_class=HTMLResponse)
async def add_schedule(
    request: Request,
    name: Annotated[str, Form()],
    day: Annotated[DayOfWeek, Form()],
    time: Annotated[str, Form()],
    program: Annotated[str, Form()],
) -> HTMLResponse:
    data = load()
    sched = Schedule(name=name, day=day, time=time, program=program)
    data.schedules.append(sched)
    save(data)
    reload_jobs()
    return templates.TemplateResponse(
        request,
        "fragments/schedule_row.html",
        {"s": sched},
    )


@router.post("/{schedule_id}/toggle", response_class=HTMLResponse)
async def toggle_schedule(request: Request, schedule_id: str) -> HTMLResponse:
    data = load()
    for s in data.schedules:
        if s.id == schedule_id:
            s.enabled = not s.enabled
            save(data)
            reload_jobs()
            return templates.TemplateResponse(
                request,
                "fragments/schedule_row.html",
                {"s": s},
            )
    return HTMLResponse("Schedule not found", status_code=404)


@router.delete("/{schedule_id}", response_class=HTMLResponse)
async def delete_schedule(schedule_id: str) -> HTMLResponse:
    data = load()
    before = len(data.schedules)
    data.schedules = [s for s in data.schedules if s.id != schedule_id]
    if len(data.schedules) == before:
        return HTMLResponse("Schedule not found", status_code=404)
    save(data)
    reload_jobs()
    return HTMLResponse("")
