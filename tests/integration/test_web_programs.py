from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)

TOKENS = TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0)

PROGRAM_LIST = [
    {"key": "Dishcare.Dishwasher.Program.Eco50"},
    {"key": "Dishcare.Dishwasher.Program.Quick45"},
]

# Matches real API shape: type + constraints with default/liveupdate
PROGRAM_DETAILS_ECO50 = {
    "key": "Dishcare.Dishwasher.Program.Eco50",
    "options": [
        {
            "key": "BSH.Common.Option.StartInRelative",
            "type": "Int",
            "unit": "seconds",
            "constraints": {"min": 0, "max": 86340},
        },
        {
            "key": "Dishcare.Dishwasher.Option.IntensivZone",
            "type": "Boolean",
            "constraints": {"default": False, "liveupdate": True},
        },
        {
            "key": "Dishcare.Dishwasher.Option.BrillianceDry",
            "type": "Boolean",
            "constraints": {"default": True, "liveupdate": True},
        },
    ],
}

PROGRAM_DETAILS_QUICK45 = {
    "key": "Dishcare.Dishwasher.Program.Quick45",
    "options": [
        {
            "key": "Dishcare.Dishwasher.Option.SilenceOnDemand",
            "type": "Boolean",
            "constraints": {"default": False, "liveupdate": True},
        },
    ],
}

# Test data with energy/water/duration for sort tests
PROGRAM_DETAILS_WITH_FORECASTS = {
    "key": "Dishcare.Dishwasher.Program.Auto2",
    "options": [
        {
            "key": "BSH.Common.Option.Duration",
            "type": "Int",
            "unit": "seconds",
            "value": 3600,
            "constraints": {"min": 1800, "max": 7200},
        },
        {
            "key": "BSH.Common.Option.EnergyForecast",
            "type": "Int",
            "unit": "%",
            "value": 50,
        },
        {
            "key": "BSH.Common.Option.WaterForecast",
            "type": "Int",
            "unit": "%",
            "value": 60,
        },
    ],
}


def _mock_client(details_map=None):
    if details_map is None:
        details_map = {
            "Eco50": PROGRAM_DETAILS_ECO50,
            "Quick45": PROGRAM_DETAILS_QUICK45,
        }
    mock_cls = patch("home_connect_scheduler.routes.programs.HomeConnectClient")
    mock = mock_cls.start()
    instance = mock.return_value
    instance.list_programs = AsyncMock(
        return_value=[{"key": d["key"]} for d in details_map.values()]
    )
    instance.get_program_details = AsyncMock(
        side_effect=lambda ha_id, key: next(v for k, v in details_map.items() if k in key)
    )
    instance.close = AsyncMock()
    return mock_cls


def test_programs_not_connected():
    with patch("home_connect_scheduler.routes.programs.load", return_value=AppData()):
        resp = client.get("/programs")
    assert resp.status_code == 200
    assert "authenticate" in resp.text.lower()


def test_programs_list():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs")
    mock_cls.stop()

    assert resp.status_code == 200
    assert "Eco 50" in resp.text
    assert "Quick 45" in resp.text
    # Options should be visible (not hidden)
    assert "Intensiv Zone" in resp.text
    assert "Brilliance Dry" in resp.text
    assert "Silence On Demand" in resp.text
    # StartInRelative should be filtered out
    assert "Start In Relative" not in resp.text


def test_programs_hides_empty_forecast_columns():
    """When API returns no energy/water/duration, those columns should not appear."""
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs")
    mock_cls.stop()

    assert resp.status_code == 200
    # No programs have duration/energy/water, so those column headers shouldn't appear
    assert "Duration" not in resp.text
    assert "Energy" not in resp.text
    assert "Water" not in resp.text


def test_programs_shows_forecast_columns_when_available():
    """When API returns energy/water/duration, those columns should appear."""
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client({"Auto2": PROGRAM_DETAILS_WITH_FORECASTS})
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs")
    mock_cls.stop()

    assert resp.status_code == 200
    assert "Duration" in resp.text
    assert "Energy" in resp.text
    assert "Water" in resp.text
    assert "30-120 min" in resp.text  # 1800-7200 seconds
    assert "50%" in resp.text
    assert "60%" in resp.text


def test_programs_sort_by_name():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs?sort=name&dir=asc")
    mock_cls.stop()

    assert resp.status_code == 200
    eco_pos = resp.text.index("Eco 50")
    quick_pos = resp.text.index("Quick 45")
    assert eco_pos < quick_pos
