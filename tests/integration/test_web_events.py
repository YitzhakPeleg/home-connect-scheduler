from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)

TOKENS = TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0)


def test_events_not_connected():
    with patch("home_connect_scheduler.routes.events.load", return_value=AppData()):
        resp = client.get("/api/events")
    assert resp.status_code == 400


def test_events_no_appliance():
    data = AppData(tokens=TOKENS)
    with patch("home_connect_scheduler.routes.events.load", return_value=data):
        resp = client.get("/api/events")
    assert resp.status_code == 400


async def _mock_events(*_args, **_kwargs):
    yield {"event": "STATUS", "data": '{"key": "DoorState", "value": "Open"}'}
    yield {"event": "KEEP-ALIVE", "data": ""}


def test_events_stream():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    with (
        patch("home_connect_scheduler.routes.events.load", return_value=data),
        patch("home_connect_scheduler.routes.events.HomeConnectClient") as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.stream_events = lambda ha_id: _mock_events()
        instance.close = AsyncMock()

        with client.stream("GET", "/api/events") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"
            lines = list(resp.iter_lines())

    # Should contain STATUS event and keepalive
    text = "\n".join(lines)
    assert "STATUS" in text
    assert "DoorState" in text
