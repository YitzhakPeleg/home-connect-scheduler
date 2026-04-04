from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from home_connect_scheduler.models import AppData, RunResult, TokenData
from home_connect_scheduler.webapp import app

client = TestClient(app)

TOKENS = TokenData(access_token="t", refresh_token="r", expires_at=9999999999.0)


def test_history_empty():
    data = AppData(tokens=TOKENS)
    with patch("home_connect_scheduler.routes.history.load", return_value=data):
        resp = client.get("/history")
    assert resp.status_code == 200
    assert "No runs recorded" in resp.text


def test_history_with_runs():
    data = AppData(
        tokens=TOKENS,
        run_log=[
            RunResult(
                schedule_id="abc",
                schedule_name="Morning",
                timestamp=datetime(2026, 4, 1, 7, 0, tzinfo=UTC),
                success=True,
                message="Program started",
            ),
            RunResult(
                schedule_id="def",
                schedule_name="Evening",
                timestamp=datetime(2026, 4, 1, 19, 0, tzinfo=UTC),
                success=False,
                message="Appliance not ready",
            ),
        ],
    )
    with patch("home_connect_scheduler.routes.history.load", return_value=data):
        resp = client.get("/history")
    assert resp.status_code == 200
    assert "Morning" in resp.text
    assert "Evening" in resp.text
    assert "Success" in resp.text
    assert "Failed" in resp.text
    assert "Appliance not ready" in resp.text
