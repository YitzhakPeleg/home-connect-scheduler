from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.store import load, save
from home_connect_scheduler.web_deps import templates

router = APIRouter(prefix="/appliances", tags=["appliances"])


@router.get("", response_class=HTMLResponse)
async def list_appliances(request: Request) -> HTMLResponse:
    data = load()
    if not data.tokens:
        return templates.TemplateResponse(
            request,
            "appliances.html",
            {"connected": False, "appliances": [], "selected": None},
        )

    client = HomeConnectClient()
    try:
        appliances = await client.list_appliances()
    except Exception:
        appliances = []
    finally:
        await client.close()

    return templates.TemplateResponse(
        request,
        "appliances.html",
        {
            "connected": True,
            "appliances": appliances,
            "selected": data.selected_appliance,
        },
    )


@router.post("/{ha_id}/select", response_class=HTMLResponse)
async def select_appliance(request: Request, ha_id: str) -> HTMLResponse:
    data = load()
    data.selected_appliance = ha_id
    save(data)

    # Re-fetch appliance list to re-render with updated selection
    client = HomeConnectClient()
    try:
        appliances = await client.list_appliances()
    except Exception:
        appliances = []
    finally:
        await client.close()

    return templates.TemplateResponse(
        request,
        "fragments/appliance_list.html",
        {"appliances": appliances, "selected": ha_id},
    )
