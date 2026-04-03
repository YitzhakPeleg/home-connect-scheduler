from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from loguru import logger

from home_connect_scheduler.models import TokenData
from home_connect_scheduler.settings import settings
from home_connect_scheduler.store import load, save


class HomeConnectClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._refresh_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    def _get_tokens(self) -> TokenData | None:
        return load().tokens

    def _save_tokens(self, tokens: TokenData) -> None:
        data = load()
        data.tokens = tokens
        save(data)

    async def _ensure_token(self) -> str:
        async with self._refresh_lock:
            tokens = self._get_tokens()
            if tokens is None:
                msg = "Not authenticated. Run 'hcs connect' first."
                raise RuntimeError(msg)
            if time.time() >= tokens.expires_at - 60:
                tokens = await self._refresh_token(tokens)
                self._save_tokens(tokens)
            return tokens.access_token

    async def _refresh_token(self, tokens: TokenData) -> TokenData:
        logger.info("Refreshing access token")
        resp = await self._client.post(
            f"{settings.api_base_url}/security/oauth/token",
            data=self._token_params(
                grant_type="refresh_token",
                refresh_token=tokens.refresh_token,
            ),
        )
        resp.raise_for_status()
        body = resp.json()
        return TokenData(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", tokens.refresh_token),
            expires_at=time.time() + body["expires_in"],
        )

    async def _headers(self) -> dict[str, str]:
        token = await self._ensure_token()
        return {"Authorization": f"Bearer {token}"}

    # --- OAuth flow ---

    def get_auth_url(self) -> str:
        params = {
            "client_id": settings.client_id,
            "redirect_uri": settings.redirect_uri,
            "response_type": "code",
            "scope": "IdentifyAppliance Dishwasher-Monitor",
        }
        return f"{settings.api_base_url}/security/oauth/authorize?{urlencode(params)}"

    def wait_for_callback(self) -> str:
        parsed = urlparse(settings.redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080

        code_holder: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                qs = parse_qs(urlparse(self.path).query)
                if "code" in qs:
                    code_holder.append(qs["code"][0])
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Authorization successful! You can close this tab.")
                elif "error" in qs:
                    error = qs["error"][0]
                    desc = qs.get("error_description", [""])[0]
                    logger.error("OAuth error: {} - {}", error, desc)
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(f"Authorization failed: {error} - {desc}".encode())
                else:
                    # Ignore favicon and other spurious requests
                    self.send_response(200)
                    self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                pass

        server = HTTPServer((host, port), Handler)

        def serve_until_code() -> None:
            while not code_holder:
                server.handle_request()

        thread = Thread(target=serve_until_code, daemon=True)
        thread.start()
        thread.join(timeout=120)
        server.server_close()

        if not code_holder:
            msg = "Timed out waiting for authorization callback."
            raise TimeoutError(msg)
        return code_holder[0]

    def _token_params(self, **extra: str) -> dict[str, str]:
        params = {"client_id": settings.client_id, **extra}
        if settings.client_secret:
            params["client_secret"] = settings.client_secret
        return params

    async def exchange_code(self, code: str) -> None:
        logger.info("Authorization code received: {}", code)
        token_data = self._token_params(
            grant_type="authorization_code",
            redirect_uri=settings.redirect_uri,
            code=code,
        )
        safe_params = {k: v for k, v in token_data.items() if k != "client_secret"}
        logger.debug("Token request params: {}", safe_params)
        resp = await self._client.post(
            f"{settings.api_base_url}/security/oauth/token",
            data=token_data,
        )
        logger.info("Token response ({}): {}", resp.status_code, resp.text)
        if resp.status_code != 200:
            logger.error("Token exchange failed ({}): {}", resp.status_code, resp.text)
            resp.raise_for_status()
        body = resp.json()
        tokens = TokenData(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_at=time.time() + body["expires_in"],
        )
        self._save_tokens(tokens)
        logger.info("Authentication successful")

    # --- Appliances ---

    async def list_appliances(self) -> list[dict[str, Any]]:
        headers = await self._headers()
        resp = await self._client.get(
            f"{settings.api_base_url}/api/homeappliances",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["data"]["homeappliances"]

    # --- Programs ---

    async def list_programs(self, ha_id: str) -> list[dict[str, Any]]:
        headers = await self._headers()
        resp = await self._client.get(
            f"{settings.api_base_url}/api/homeappliances/{ha_id}/programs/available",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["data"]["programs"]

    async def get_status(self, ha_id: str) -> dict[str, Any]:
        headers = await self._headers()
        resp = await self._client.get(
            f"{settings.api_base_url}/api/homeappliances/{ha_id}/status",
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["data"]["status"]

    async def start_program(
        self, ha_id: str, program_key: str, options: list[dict[str, Any]] | None = None
    ) -> None:
        headers = await self._headers()
        headers["Content-Type"] = "application/json"
        payload: dict[str, Any] = {"data": {"key": program_key}}
        if options:
            payload["data"]["options"] = options
        resp = await self._client.put(
            f"{settings.api_base_url}/api/homeappliances/{ha_id}/programs/active",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        logger.info("Started program {}", program_key)

    # --- Events (SSE) ---

    async def stream_events(self, ha_id: str) -> AsyncIterator[dict[str, str]]:
        """Stream Server-Sent Events from the Home Connect API.

        Yields dicts with keys: 'event', 'data', 'id' (when present).
        """
        headers = await self._headers()
        headers["Accept"] = "text/event-stream"
        async with self._client.stream(
            "GET",
            f"{settings.api_base_url}/api/homeappliances/{ha_id}/events",
            headers=headers,
            timeout=None,
        ) as response:
            response.raise_for_status()
            event: dict[str, str] = {}
            async for line in response.aiter_lines():
                if not line:
                    if event:
                        yield event
                        event = {}
                    continue
                if line.startswith("event:"):
                    event["event"] = line[6:].strip()
                elif line.startswith("data:"):
                    event["data"] = line[5:].strip()
                elif line.startswith("id:"):
                    event["id"] = line[3:].strip()
