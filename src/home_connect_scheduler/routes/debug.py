from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.store import load

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/programs", response_class=JSONResponse)
async def debug_programs() -> JSONResponse:
    """Dump raw program details from the Home Connect API for debugging."""
    data = load()
    if not data.tokens or not data.selected_appliance:
        return JSONResponse({"error": "Not connected or no appliance selected"}, status_code=400)

    client = HomeConnectClient()
    try:
        program_list = await client.list_programs(data.selected_appliance)
        tasks = [
            client.get_program_details(data.selected_appliance, p["key"]) for p in program_list
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        programs: list[dict[str, Any]] = []
        for r in results:
            if isinstance(r, Exception):
                programs.append({"error": str(r)})
            else:
                programs.append(r)
        return JSONResponse({"programs": programs})
    finally:
        await client.close()
