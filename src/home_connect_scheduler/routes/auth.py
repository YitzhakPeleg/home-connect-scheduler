from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from home_connect_scheduler.homeconnect import HomeConnectClient

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login() -> RedirectResponse:
    client = HomeConnectClient()
    url = client.get_auth_url()
    return RedirectResponse(url)


@router.get("/callback")
async def callback(request: Request, code: str) -> RedirectResponse:
    client = HomeConnectClient()
    try:
        await client.exchange_code(code)
    finally:
        await client.close()
    return RedirectResponse("/", status_code=303)
