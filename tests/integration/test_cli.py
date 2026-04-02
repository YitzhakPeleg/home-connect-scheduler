from unittest.mock import patch

from typer.testing import CliRunner

from home_connect_scheduler.cli import app
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
