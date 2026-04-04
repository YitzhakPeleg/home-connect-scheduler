from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from home_connect_scheduler.webapp import app

client = TestClient(app, follow_redirects=False)


def test_login_redirects_to_homeconnect():
    resp = client.get("/auth/login")
    assert resp.status_code == 307
    assert "oauth/authorize" in resp.headers["location"]
    assert "client_id=" in resp.headers["location"]


def test_callback_exchanges_code_and_redirects():
    with patch("home_connect_scheduler.routes.auth.HomeConnectClient") as mock_cls:
        instance = mock_cls.return_value
        instance.exchange_code = AsyncMock()
        instance.close = AsyncMock()

        resp = client.get("/auth/callback?code=test-auth-code")

    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    instance.exchange_code.assert_awaited_once_with("test-auth-code")
    instance.close.assert_awaited_once()


def test_callback_missing_code_returns_422():
    resp = client.get("/auth/callback")
    assert resp.status_code == 422
