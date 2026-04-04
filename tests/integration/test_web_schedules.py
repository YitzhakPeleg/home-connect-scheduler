from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, DayOfWeek, Schedule, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)

TOKENS = TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0)


def _data_with_schedule() -> AppData:
    return AppData(
        tokens=TOKENS,
        selected_appliance="BOSCH-123",
        schedules=[
            Schedule(
                id="abc123",
                name="Morning",
                day=DayOfWeek.MON,
                time="07:00",
                program="Dishcare.Program.Auto2",
            ),
        ],
    )


def test_schedules_page_lists_schedules():
    data = _data_with_schedule()
    with (
        patch("home_connect_scheduler.routes.schedules.load", return_value=data),
        patch("home_connect_scheduler.routes.schedules.HomeConnectClient") as mock_cls,
    ):
        from unittest.mock import AsyncMock

        instance = mock_cls.return_value
        instance.list_programs = AsyncMock(return_value=[])
        instance.close = AsyncMock()
        resp = client.get("/schedules")
    assert resp.status_code == 200
    assert "Morning" in resp.text
    assert "MON" in resp.text
    assert "07:00" in resp.text


def test_add_schedule():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    with (
        patch("home_connect_scheduler.routes.schedules.load", return_value=data),
        patch("home_connect_scheduler.routes.schedules.save") as mock_save,
    ):
        resp = client.post(
            "/schedules",
            data={
                "name": "Evening",
                "day": "tue",
                "time": "19:00",
                "program": "Dishcare.Program.Eco50",
            },
        )
    assert resp.status_code == 200
    assert "Evening" in resp.text
    assert "TUE" in resp.text
    saved = mock_save.call_args[0][0]
    assert len(saved.schedules) == 1
    assert saved.schedules[0].name == "Evening"


def test_toggle_schedule():
    data = _data_with_schedule()
    assert data.schedules[0].enabled is True
    with (
        patch("home_connect_scheduler.routes.schedules.load", return_value=data),
        patch("home_connect_scheduler.routes.schedules.save"),
    ):
        resp = client.post("/schedules/abc123/toggle")
    assert resp.status_code == 200
    assert "Enable" in resp.text  # was enabled, now disabled -> button says "Enable"
    assert data.schedules[0].enabled is False


def test_toggle_schedule_not_found():
    with patch("home_connect_scheduler.routes.schedules.load", return_value=AppData(tokens=TOKENS)):
        resp = client.post("/schedules/nonexistent/toggle")
    assert resp.status_code == 404


def test_delete_schedule():
    data = _data_with_schedule()
    with (
        patch("home_connect_scheduler.routes.schedules.load", return_value=data),
        patch("home_connect_scheduler.routes.schedules.save") as mock_save,
    ):
        resp = client.delete("/schedules/abc123")
    assert resp.status_code == 200
    assert resp.text == ""
    saved = mock_save.call_args[0][0]
    assert len(saved.schedules) == 0


def test_delete_schedule_not_found():
    with patch("home_connect_scheduler.routes.schedules.load", return_value=AppData(tokens=TOKENS)):
        resp = client.delete("/schedules/nonexistent")
    assert resp.status_code == 404
