from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from home_connect_scheduler.cli import app, main
from home_connect_scheduler.models import AppData, DayOfWeek, Schedule

runner = CliRunner()


def _mock_store(data: AppData | None = None):
    """Return patches for load/save against a given AppData."""
    if data is None:
        data = AppData()
    return (
        patch("home_connect_scheduler.cli.load", return_value=data),
        patch("home_connect_scheduler.cli.save"),
    )


class TestScheduleAdd:
    def test_add_schedule(self):
        data = AppData()
        with (
            patch("home_connect_scheduler.cli.load", return_value=data),
            patch("home_connect_scheduler.cli.save") as mock_save,
        ):
            result = runner.invoke(
                app,
                [
                    "schedule",
                    "add",
                    "--name",
                    "Shabbat eco",
                    "--day",
                    "sat",
                    "--time",
                    "01:00",
                    "--program",
                    "Dishcare.Program.Eco50",
                ],
            )
            assert result.exit_code == 0
            assert "Added schedule" in result.output
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert len(saved.schedules) == 1
            assert saved.schedules[0].name == "Shabbat eco"


class TestScheduleList:
    def test_empty(self):
        p1, p2 = _mock_store()
        with p1, p2:
            result = runner.invoke(app, ["schedule", "list"])
            assert result.exit_code == 0
            assert "No schedules" in result.output

    def test_with_schedules(self):
        data = AppData(
            schedules=[
                Schedule(name="eco", day=DayOfWeek.SAT, time="01:00", program="p"),
            ]
        )
        p1, p2 = _mock_store(data)
        with p1, p2:
            result = runner.invoke(app, ["schedule", "list"])
            assert result.exit_code == 0
            assert "eco" in result.output


class TestScheduleRemove:
    def test_remove_existing(self):
        sched = Schedule(name="eco", day=DayOfWeek.SAT, time="01:00", program="p")
        data = AppData(schedules=[sched])
        with (
            patch("home_connect_scheduler.cli.load", return_value=data),
            patch("home_connect_scheduler.cli.save"),
        ):
            result = runner.invoke(app, ["schedule", "remove", sched.id])
            assert result.exit_code == 0
            assert "Removed" in result.output

    def test_remove_nonexistent(self):
        p1, p2 = _mock_store()
        with p1, p2:
            result = runner.invoke(app, ["schedule", "remove", "nonexistent"])
            assert result.exit_code == 1


class TestScheduleToggle:
    def test_toggle(self):
        sched = Schedule(name="eco", day=DayOfWeek.SAT, time="01:00", program="p")
        assert sched.enabled is True
        data = AppData(schedules=[sched])
        with (
            patch("home_connect_scheduler.cli.load", return_value=data),
            patch("home_connect_scheduler.cli.save"),
        ):
            result = runner.invoke(app, ["schedule", "toggle", sched.id])
            assert result.exit_code == 0
            assert "disabled" in result.output


class TestStatus:
    def test_no_schedules(self):
        p1, p2 = _mock_store()
        with p1, p2:
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "No schedules" in result.output

    def test_with_schedules(self):
        data = AppData(
            schedules=[
                Schedule(name="eco", day=DayOfWeek.SAT, time="01:00", program="p"),
            ]
        )
        p1, p2 = _mock_store(data)
        with p1, p2:
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "eco" in result.output


class TestSelectAppliance:
    def test_select(self):
        with (
            patch("home_connect_scheduler.cli.load", return_value=AppData()),
            patch("home_connect_scheduler.cli.save") as mock_save,
        ):
            result = runner.invoke(app, ["select", "BOSCH-123"])
            assert result.exit_code == 0
            assert "BOSCH-123" in result.output
            saved = mock_save.call_args[0][0]
            assert saved.selected_appliance == "BOSCH-123"


class TestApplianceStatus:
    def _mock_client(self, status_items, active_program=None):
        """Create a mock HomeConnectClient for appliance-status tests."""
        import httpx

        mock = AsyncMock()
        mock.get_status.return_value = status_items
        mock._headers.return_value = {"Authorization": "Bearer test"}
        mock.close.return_value = None

        if active_program:
            resp = httpx.Response(200, json={"data": active_program})
        else:
            resp = httpx.Response(404)
        mock._client.get.return_value = resp
        return mock

    def test_no_appliance_selected(self):
        p1, p2 = _mock_store()
        with p1, p2:
            result = runner.invoke(app, ["appliance-status"])
            assert result.exit_code == 1
            assert "No appliance selected" in result.output

    def test_status_only(self):
        data = AppData(selected_appliance="BOSCH-123")
        status = [
            {
                "key": "BSH.Common.Status.OperationState",
                "value": "BSH.Common.EnumType.OperationState.Inactive",
            },
            {
                "key": "BSH.Common.Status.DoorState",
                "value": "BSH.Common.EnumType.DoorState.Closed",
            },
        ]
        mock_client = self._mock_client(status)
        with (
            patch("home_connect_scheduler.cli.load", return_value=data),
            patch("home_connect_scheduler.cli.HomeConnectClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["appliance-status"])
            assert result.exit_code == 0
            assert "Inactive" in result.output
            assert "Closed" in result.output

    def test_with_active_program(self):
        data = AppData(selected_appliance="BOSCH-123")
        status = [
            {
                "key": "BSH.Common.Status.OperationState",
                "value": "BSH.Common.EnumType.OperationState.Run",
            },
        ]
        active = {
            "key": "Dishcare.Dishwasher.Program.Eco50",
            "options": [
                {"key": "BSH.Common.Option.ProgramProgress", "value": 42, "unit": "%"},
                {"key": "BSH.Common.Option.RemainingProgramTime", "value": 7200, "unit": "seconds"},
                {"key": "Dishcare.Dishwasher.Option.EcoDry", "value": True},
            ],
        }
        mock_client = self._mock_client(status, active)
        with (
            patch("home_connect_scheduler.cli.load", return_value=data),
            patch("home_connect_scheduler.cli.HomeConnectClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["appliance-status"])
            assert result.exit_code == 0
            assert "Eco50" in result.output
            assert "42%" in result.output
            assert "2h 0m" in result.output
            assert "True" in result.output

    def test_time_format_minutes_only(self):
        data = AppData(selected_appliance="BOSCH-123")
        status = [{"key": "BSH.Common.Status.OperationState", "value": "Run"}]
        active = {
            "key": "Program.Quick",
            "options": [
                {"key": "BSH.Common.Option.RemainingProgramTime", "value": 1800, "unit": "seconds"},
            ],
        }
        mock_client = self._mock_client(status, active)
        with (
            patch("home_connect_scheduler.cli.load", return_value=data),
            patch("home_connect_scheduler.cli.HomeConnectClient", return_value=mock_client),
        ):
            result = runner.invoke(app, ["appliance-status"])
            assert result.exit_code == 0
            assert "30m" in result.output


class TestMainErrorHandler:
    def test_unhandled_exception(self):
        with patch("home_connect_scheduler.cli.app", side_effect=RuntimeError("boom")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_keyboard_interrupt(self):
        with patch("home_connect_scheduler.cli.app", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 130

    def test_typer_exit_passes_through(self):
        import typer

        with patch("home_connect_scheduler.cli.app", side_effect=typer.Exit(0)):
            try:
                main()
            except typer.Exit as e:
                assert e.exit_code == 0
