from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)

TOKENS = TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0)
APPLIANCES = [
    {"haId": "BOSCH-001", "type": "Dishwasher", "name": "Kitchen", "brand": "Bosch"},
    {"haId": "BOSCH-002", "type": "Oven", "name": "Oven", "brand": "Bosch"},
]


def test_appliances_not_connected():
    with patch("home_connect_scheduler.routes.appliances.load", return_value=AppData()):
        resp = client.get("/appliances")
    assert resp.status_code == 200
    assert "authenticate" in resp.text.lower()


def test_appliances_list():
    data = AppData(tokens=TOKENS)
    with (
        patch("home_connect_scheduler.routes.appliances.load", return_value=data),
        patch("home_connect_scheduler.routes.appliances.HomeConnectClient") as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.list_appliances = AsyncMock(return_value=APPLIANCES)
        instance.close = AsyncMock()
        resp = client.get("/appliances")
    assert resp.status_code == 200
    assert "BOSCH-001" in resp.text
    assert "BOSCH-002" in resp.text
    assert "Kitchen" in resp.text


def test_appliances_select():
    data = AppData(tokens=TOKENS)
    with (
        patch("home_connect_scheduler.routes.appliances.load", return_value=data),
        patch("home_connect_scheduler.routes.appliances.save") as mock_save,
        patch("home_connect_scheduler.routes.appliances.HomeConnectClient") as mock_cls,
    ):
        instance = mock_cls.return_value
        instance.list_appliances = AsyncMock(return_value=APPLIANCES)
        instance.close = AsyncMock()
        resp = client.post("/appliances/BOSCH-001/select")

    assert resp.status_code == 200
    assert "Selected" in resp.text
    saved_data = mock_save.call_args[0][0]
    assert saved_data.selected_appliance == "BOSCH-001"
