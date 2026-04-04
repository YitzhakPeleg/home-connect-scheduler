from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from home_connect_scheduler.models import Schedule
from home_connect_scheduler.scheduler import DAY_MAP, _execute_schedule_async
from home_connect_scheduler.store import load

_scheduler: AsyncIOScheduler | None = None


async def _run_schedule(schedule: Schedule, ha_id: str) -> None:
    """Wrapper for async execution within the AsyncIOScheduler."""
    await _execute_schedule_async(schedule, ha_id)


def _load_jobs(scheduler: AsyncIOScheduler) -> None:
    data = load()
    if not data.selected_appliance:
        logger.warning("No appliance selected — scheduler has no jobs")
        return

    ha_id = data.selected_appliance
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
            _run_schedule,
            trigger=trigger,
            args=[sched, ha_id],
            id=sched.id,
            name=sched.name,
            replace_existing=True,
        )
        logger.info("Scheduled '{}' for {} at {}", sched.name, sched.day.value, sched.time)


def start_web_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler(misfire_grace_time=300)
    _load_jobs(_scheduler)
    _scheduler.start()
    logger.info("AsyncIO scheduler started with {} job(s)", len(_scheduler.get_jobs()))


def stop_web_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def reload_jobs() -> None:
    """Reload all jobs from data file. Call after schedule changes."""
    if not _scheduler:
        return
    _scheduler.remove_all_jobs()
    _load_jobs(_scheduler)
