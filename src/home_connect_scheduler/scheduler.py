from __future__ import annotations

import asyncio
import signal
import sys
from datetime import UTC, datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from home_connect_scheduler.homeconnect import HomeConnectClient
from home_connect_scheduler.models import DayOfWeek, RunResult, Schedule
from home_connect_scheduler.store import load, save

DAY_MAP: dict[DayOfWeek, str] = {
    DayOfWeek.MON: "mon",
    DayOfWeek.TUE: "tue",
    DayOfWeek.WED: "wed",
    DayOfWeek.THU: "thu",
    DayOfWeek.FRI: "fri",
    DayOfWeek.SAT: "sat",
    DayOfWeek.SUN: "sun",
}

# Retry config
MAX_RETRIES_409 = 3
RETRY_INTERVAL_409 = 120  # seconds

MAX_RETRIES_429 = 5
RETRY_BASE_429 = 30  # seconds — Home Connect rate limit resets ~every minute

MAX_RETRIES_NETWORK = 3
NETWORK_BACKOFF_BASE = 2  # seconds


def _get_status_code(exc: Exception) -> int | None:
    return getattr(getattr(exc, "response", None), "status_code", None)


def _get_retry_after(exc: Exception) -> int | None:
    """Extract Retry-After header from httpx response if present."""
    response = getattr(exc, "response", None)
    if response is not None:
        val = response.headers.get("Retry-After")
        if val and val.isdigit():
            return int(val)
    return None


def _log_result(schedule: Schedule, success: bool, message: str) -> None:
    data = load()
    result = RunResult(
        schedule_id=schedule.id,
        schedule_name=schedule.name,
        timestamp=datetime.now(tz=UTC),
        success=success,
        message=message,
    )
    data.run_log.append(result)
    save(data)


async def _try_start(client: HomeConnectClient, ha_id: str, schedule: Schedule) -> None:
    options = [opt.model_dump(exclude_none=True) for opt in schedule.options] or None
    await client.start_program(ha_id, schedule.program, options)


async def _execute_schedule_async(schedule: Schedule, ha_id: str) -> None:
    client = HomeConnectClient()
    try:
        for attempt in range(max(MAX_RETRIES_409, MAX_RETRIES_429, MAX_RETRIES_NETWORK)):
            try:
                await _try_start(client, ha_id, schedule)
                _log_result(schedule, success=True, message="Program started")
                logger.info("Schedule '{}' executed successfully", schedule.name)
                return
            except Exception as exc:
                status_code = _get_status_code(exc)

                if status_code == 409:
                    if attempt < MAX_RETRIES_409 - 1:
                        logger.warning(
                            "Appliance not ready (409), retry {}/{} in {}s",
                            attempt + 1,
                            MAX_RETRIES_409,
                            RETRY_INTERVAL_409,
                        )
                        await asyncio.sleep(RETRY_INTERVAL_409)
                        continue
                    _log_result(
                        schedule,
                        success=False,
                        message=f"Appliance not ready after {MAX_RETRIES_409} retries",
                    )
                    logger.error("Schedule '{}' failed: appliance not ready", schedule.name)
                    return

                if status_code == 429:
                    retry_after = _get_retry_after(exc) or RETRY_BASE_429 * (2**attempt)
                    if attempt < MAX_RETRIES_429 - 1:
                        logger.warning(
                            "Rate limited (429), retry {}/{} in {}s",
                            attempt + 1,
                            MAX_RETRIES_429,
                            retry_after,
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    _log_result(
                        schedule,
                        success=False,
                        message=f"Rate limited after {MAX_RETRIES_429} retries",
                    )
                    logger.error("Schedule '{}' failed: rate limited", schedule.name)
                    return

                # Network / other errors
                if attempt < MAX_RETRIES_NETWORK - 1:
                    delay = NETWORK_BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Error ({}), retry {}/{} in {}s",
                        exc,
                        attempt + 1,
                        MAX_RETRIES_NETWORK,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                _log_result(schedule, success=False, message=f"Error: {exc}")
                logger.error("Schedule '{}' failed: {}", schedule.name, exc)
                return
    finally:
        await client.close()


def execute_schedule(schedule: Schedule, ha_id: str) -> None:
    asyncio.run(_execute_schedule_async(schedule, ha_id))


def start_scheduler() -> None:
    data = load()
    if not data.selected_appliance:
        logger.error("No appliance selected. Run 'hcs select <haId>' first.")
        sys.exit(1)

    ha_id = data.selected_appliance
    scheduler = BlockingScheduler(misfire_grace_time=300)

    for sched in data.schedules:
        if not sched.enabled:
            continue
        hour, minute = sched.time.split(":")
        trigger = CronTrigger(
            day_of_week=DAY_MAP[sched.day],
            hour=int(hour),
            minute=int(minute),
        )
        scheduler.add_job(
            execute_schedule,
            trigger=trigger,
            args=[sched, ha_id],
            id=sched.id,
            name=sched.name,
        )
        logger.info("Scheduled '{}' for {} at {}", sched.name, sched.day.value, sched.time)

    def shutdown(signum: int, frame: object) -> None:
        logger.info("Received signal {}, shutting down...", signum)
        scheduler.shutdown(wait=True)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("Scheduler started with {} active schedule(s)", len(scheduler.get_jobs()))
    scheduler.start()
