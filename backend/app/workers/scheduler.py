from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import settings
from ..db import SessionLocal
from ..services.arxiv_fetch import fetch_subscriptions
from .queue import enqueue_light_for_new_paper

log = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def run_fetch_now() -> tuple[int, int]:
    """Run fetch synchronously; return (new_paper_count, queued_jobs)."""
    with SessionLocal() as db:
        new_ids = fetch_subscriptions(db)
    for pid in new_ids:
        enqueue_light_for_new_paper(pid)
    return len(new_ids), 2 * len(new_ids)


async def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sched = AsyncIOScheduler()
    sched.add_job(
        run_fetch_now,
        CronTrigger(hour=settings.FETCH_CRON_HOUR, minute=settings.FETCH_CRON_MINUTE),
        id="daily_fetch",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    log.info(
        "Scheduler started: daily fetch at %02d:%02d",
        settings.FETCH_CRON_HOUR,
        settings.FETCH_CRON_MINUTE,
    )
    return sched


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
