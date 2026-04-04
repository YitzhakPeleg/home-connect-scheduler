from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)


def test_dashboard_not_connected():
    with patch("home_connect_scheduler.webapp.load", return_value=AppData()):
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Not Connected" in resp.text
    assert "Connect Now" in resp.text


def test_dashboard_connected_no_appliance():
    data = AppData(tokens=TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0))
    with patch("home_connect_scheduler.webapp.load", return_value=data):
        resp = client.get("/")
    assert resp.status_code == 200
    assert "Authenticated" in resp.text
    assert "No appliance selected" in resp.text


def test_dashboard_connected_with_appliance():
    data = AppData(
        tokens=TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0),
        selected_appliance="BOSCH-123",
    )
    with patch("home_connect_scheduler.webapp.load", return_value=data):
        resp = client.get("/")
    assert resp.status_code == 200
    assert "BOSCH-123" in resp.text
    assert "status-card" in resp.text
