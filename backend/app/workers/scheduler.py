from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..db import SessionLocal
from ..services.arxiv_fetch import fetch_subscriptions
from ..services.app_settings import (
    HEAVY_PROCESSING_ON_FETCH,
    get_auto_fetch_enabled,
    get_fetch_time,
    get_heavy_processing_trigger,
    parse_fetch_time,
)
from .queue import enqueue_heavy_for_to_read, enqueue_light_for_new_paper

log = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None
FETCH_JOB_ID = "daily_fetch"


def run_fetch_now() -> tuple[int, int]:
    """Run fetch synchronously; return (new_paper_count, queued_jobs)."""
    with SessionLocal() as db:
        new_ids = fetch_subscriptions(db)
        heavy_on_fetch = get_heavy_processing_trigger(db) == HEAVY_PROCESSING_ON_FETCH
    queued = 0
    for pid in new_ids:
        enqueue_light_for_new_paper(pid)
        queued += 2
        if heavy_on_fetch:
            enqueue_heavy_for_to_read(pid)
            queued += 2
    return len(new_ids), queued


def _load_schedule_config() -> tuple[bool, str]:
    with SessionLocal() as db:
        return get_auto_fetch_enabled(db), get_fetch_time(db)


def _configure_fetch_job(sched: AsyncIOScheduler) -> None:
    enabled, fetch_time = _load_schedule_config()
    existing = sched.get_job(FETCH_JOB_ID)
    if existing is not None:
        sched.remove_job(FETCH_JOB_ID)

    if not enabled:
        log.info("Scheduler configured: daily fetch disabled")
        return

    hour, minute = parse_fetch_time(fetch_time)
    sched.add_job(
        run_fetch_now,
        CronTrigger(hour=hour, minute=minute),
        id=FETCH_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("Scheduler configured: daily fetch at %s", fetch_time)


def reload_scheduler() -> None:
    if _scheduler is None:
        return
    _configure_fetch_job(_scheduler)


async def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = AsyncIOScheduler()
    _configure_fetch_job(sched)
    sched.start()
    _scheduler = sched
    log.info("Scheduler started")
    return sched


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
