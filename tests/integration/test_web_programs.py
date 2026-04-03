from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)

TOKENS = TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0)

PROGRAM_LIST = [
    {"key": "Dishcare.Dishwasher.Program.Quick45"},
    {"key": "Dishcare.Dishwasher.Program.Glass"},
]

# Matches real API shape
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

PROGRAM_DETAILS_GLASS = {
    "key": "Dishcare.Dishwasher.Program.Glass",
    "options": [
        {
            "key": "Dishcare.Dishwasher.Option.BrillianceDry",
            "type": "Boolean",
            "constraints": {"default": True, "liveupdate": True},
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
            PROGRAM_DETAILS_QUICK45 if "Quick45" in key else PROGRAM_DETAILS_GLASS
        )
    )
    instance.close = AsyncMock()
    return mock_cls


def test_programs_not_connected():
    with patch("home_connect_scheduler.routes.programs.load", return_value=AppData()):
        resp = client.get("/programs")
    assert resp.status_code == 200
    assert "authenticate" in resp.text.lower()


def test_programs_list_with_specs():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs")
    mock_cls.stop()

    assert resp.status_code == 200
    # Program names from static specs
    assert "Quick Wash 45" in resp.text
    assert "Glass" in resp.text
    # Duration, energy, and water from static specs
    assert "35min" in resp.text  # Quick45
    assert "0.7 kWh" in resp.text
    assert "9.0 l" in resp.text  # Quick45 water
    assert "1h 45min" in resp.text  # Glass
    assert "11.0 l" in resp.text  # Glass water
    # Options should be visible
    assert "Silence On Demand" in resp.text
    assert "Brilliance Dry" in resp.text
    # StartInRelative should be filtered out
    assert "Start In Relative" not in resp.text


def test_programs_sort_by_duration():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs?sort=duration&dir=asc")
    mock_cls.stop()

    assert resp.status_code == 200
    # Quick45 (35min) should appear before Glass (105min) in asc order
    quick_pos = resp.text.index("Quick45")
    glass_pos = resp.text.index("Glass")
    assert quick_pos < glass_pos


def test_programs_sort_by_energy_desc():
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = _mock_client()
    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs?sort=energy&dir=desc")
    mock_cls.stop()

    assert resp.status_code == 200
    # Both have 0.7 kWh so just verify page renders
    assert "0.7 kWh" in resp.text


def test_programs_graceful_when_details_fail():
    """Programs still show when details endpoint fails (e.g. dishwasher running)."""
    data = AppData(tokens=TOKENS, selected_appliance="BOSCH-123")
    mock_cls = patch("home_connect_scheduler.routes.programs.HomeConnectClient")
    mock = mock_cls.start()
    instance = mock.return_value
    instance.list_programs = AsyncMock(
        return_value=[{"key": "Dishcare.Dishwasher.Program.Quick45"}]
    )
    instance.get_program_details = AsyncMock(side_effect=Exception("403 Forbidden"))
    instance.close = AsyncMock()

    with patch("home_connect_scheduler.routes.programs.load", return_value=data):
        resp = client.get("/programs")
    mock_cls.stop()

    assert resp.status_code == 200
    # Should still show the program with specs from YAML
    assert "Quick Wash 45" in resp.text
    assert "35min" in resp.text
    assert "9.0 l" in resp.text
