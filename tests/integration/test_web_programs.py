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

PROGRAM_DETAILS_ECO50 = {
    "key": "Dishcare.Dishwasher.Program.Eco50",
    "options": [
        {
            "key": "BSH.Common.Option.FinishInRelative",
            "value": 0,
            "unit": "seconds",
            "constraints": {"min": 0, "max": 86340},
        },
        {
            "key": "BSH.Common.Option.EnergyForecast",
            "value": 20,
            "unit": "%",
        },
        {
            "key": "BSH.Common.Option.WaterForecast",
            "value": 40,
            "unit": "%",
        },
        {
            "key": "Dishcare.Dishwasher.Option.IntensivZone",
            "value": False,
        },
        {
            "key": "Dishcare.Dishwasher.Option.BrillianceDry",
            "value": True,
        },
    ],
}

PROGRAM_DETAILS_QUICK45 = {
    "key": "Dishcare.Dishwasher.Program.Quick45",
    "options": [
        {
            "key": "BSH.Common.Option.Duration",
            "value": 2700,
            "unit": "seconds",
            "constraints": {"min": 2700, "max": 2700},
        },
        {
            "key": "BSH.Common.Option.EnergyForecast",
            "value": 60,
            "unit": "%",
        },
        {
            "key": "BSH.Common.Option.WaterForecast",
            "value": 70,
            "unit": "%",
        },
    ],
}


def _mock_client():
    mock_cls = patch("home_connect_scheduler.routes.programs.HomeConnectClient")
    mock = mock_cls.start()
    instance = mock.return_value
    instance.list_programs = AsyncMock(return_value=PROGRAM_LIST)
    instance.get_program_details = AsyncMock(
        side_effect=lambda ha_id, key: (
            PROGRAM_DETAILS_ECO50 if "Eco50" in key else PROGRAM_DETAILS_QUICK45
        )
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
    # Check options are present
    assert "Intensiv Zone" in resp.text
    assert "Brilliance Dry" in resp.text
    # Check energy/water forecasts
    assert "20%" in resp.text
    assert "40%" in resp.text


def test_programs_sort_by_energy():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs?sort=energy&dir=asc")
    mock_cls.stop()

    assert resp.status_code == 200
    # Eco50 (energy=20) should appear before Quick45 (energy=60) in asc order
    eco_pos = resp.text.index("Eco 50")
    quick_pos = resp.text.index("Quick 45")
    assert eco_pos < quick_pos


def test_programs_sort_by_water_desc():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs?sort=water&dir=desc")
    mock_cls.stop()

    assert resp.status_code == 200
    # Quick45 (water=70) should appear before Eco50 (water=40) in desc order
    quick_pos = resp.text.index("Quick 45")
    eco_pos = resp.text.index("Eco 50")
    assert quick_pos < eco_pos


def test_programs_sort_by_duration():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs?sort=duration&dir=asc")
    mock_cls.stop()

    assert resp.status_code == 200
    # Quick45 has duration_min=2700, Eco50 has duration from FinishInRelative min=0
    # Both should render without error
    assert "Quick 45" in resp.text
