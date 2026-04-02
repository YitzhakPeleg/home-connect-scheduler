from unittest.mock import AsyncMock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger

from home_connect_scheduler.models import DayOfWeek, Schedule
from home_connect_scheduler.scheduler import DAY_MAP, _execute_schedule_async


class TestDayMap:
    def test_all_days_mapped(self):
        for day in DayOfWeek:
            assert day in DAY_MAP

    def test_cron_trigger_creation(self):
        sched = Schedule(name="eco", day=DayOfWeek.SAT, time="01:30", program="p")
        hour, minute = sched.time.split(":")
        trigger = CronTrigger(
            day_of_week=DAY_MAP[sched.day],
            hour=int(hour),
            minute=int(minute),
        )
        # Verify trigger was created without error
        assert trigger is not None


class TestExecuteSchedule:
    @pytest.mark.asyncio
    async def test_success(self):
        sched = Schedule(
            name="eco", day=DayOfWeek.SAT, time="01:00", program="Dishcare.Program.Eco50"
        )

        with (
            patch("home_connect_scheduler.scheduler.HomeConnectClient") as MockClient,
            patch("home_connect_scheduler.scheduler.load") as mock_load,
            patch("home_connect_scheduler.scheduler.save") as mock_save,
        ):
            from home_connect_scheduler.models import AppData

            mock_load.return_value = AppData()
            client_instance = MockClient.return_value
            client_instance.start_program = AsyncMock()
            client_instance.close = AsyncMock()

            await _execute_schedule_async(sched, "BOSCH-123")

            client_instance.start_program.assert_called_once()
            mock_save.assert_called_once()
            saved_data = mock_save.call_args[0][0]
            assert len(saved_data.run_log) == 1
            assert saved_data.run_log[0].success is True

    @pytest.mark.asyncio
    async def test_409_retries(self):
        import httpx

        sched = Schedule(name="eco", day=DayOfWeek.SAT, time="01:00", program="p")

        mock_response = httpx.Response(409, request=httpx.Request("PUT", "http://test"))
        error = httpx.HTTPStatusError(
            "not ready", request=mock_response.request, response=mock_response
        )

        with (
            patch("home_connect_scheduler.scheduler.HomeConnectClient") as MockClient,
            patch("home_connect_scheduler.scheduler.load") as mock_load,
            patch("home_connect_scheduler.scheduler.save") as mock_save,
            patch("home_connect_scheduler.scheduler.RETRY_INTERVAL_409", 0),  # no delay in tests
        ):
            from home_connect_scheduler.models import AppData

            mock_load.return_value = AppData()
            client_instance = MockClient.return_value
            client_instance.start_program = AsyncMock(side_effect=error)
            client_instance.close = AsyncMock()

            await _execute_schedule_async(sched, "BOSCH-123")

            assert client_instance.start_program.call_count == 3  # MAX_RETRIES_409
            mock_save.assert_called_once()
            saved_data = mock_save.call_args[0][0]
            assert saved_data.run_log[0].success is False

    @pytest.mark.asyncio
    async def test_network_error_retries(self):
        sched = Schedule(name="eco", day=DayOfWeek.SAT, time="01:00", program="p")

        with (
            patch("home_connect_scheduler.scheduler.HomeConnectClient") as MockClient,
            patch("home_connect_scheduler.scheduler.load") as mock_load,
            patch("home_connect_scheduler.scheduler.save") as mock_save,
            patch("home_connect_scheduler.scheduler.NETWORK_BACKOFF_BASE", 0),
        ):
            from home_connect_scheduler.models import AppData

            mock_load.return_value = AppData()
            client_instance = MockClient.return_value
            client_instance.start_program = AsyncMock(side_effect=ConnectionError("timeout"))
            client_instance.close = AsyncMock()

            await _execute_schedule_async(sched, "BOSCH-123")

            mock_save.assert_called()
            # Find the final log result
            last_save = mock_save.call_args_list[-1][0][0]
            assert any(not r.success for r in last_save.run_log)
