"""Persistent in-process background job queue.

- Jobs are persisted to the ``jobs`` SQLite table so they survive restarts.
- Workers are asyncio coroutines; on lifespan startup we re-enqueue every job
  in ``running`` (reset to ``pending``) and every existing ``pending`` row.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Job, JobKind, JobStatus, PaperStatus, Paper
from ..services import figure_extractor, summarizer, tagger, translator

log = logging.getLogger(__name__)

# (kind) -> handler(db, paper_id) coroutine
HandlerFn = Callable[[Session, int], Awaitable[None]]


async def _run_translate(db: Session, paper_id: int) -> None:
    await translator.translate_abstract(db, paper_id)


async def _run_tag(db: Session, paper_id: int) -> None:
    await tagger.auto_tag(db, paper_id)


async def _run_summary(db: Session, paper_id: int) -> None:
    await summarizer.summarize(db, paper_id)


async def _run_figures(db: Session, paper_id: int) -> None:
    await figure_extractor.extract_figures(db, paper_id)


HANDLERS: dict[JobKind, HandlerFn] = {
    JobKind.TRANSLATE: _run_translate,
    JobKind.TAG: _run_tag,
    JobKind.SUMMARY: _run_summary,
    JobKind.FIGURES: _run_figures,
}


class JobQueue:
    def __init__(self, concurrency: int) -> None:
        self.concurrency = concurrency
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._stopping = False

    async def start(self) -> None:
        # Recover pending/running jobs
        with SessionLocal() as db:
            db.execute(
                update(Job)
                .where(Job.status == JobStatus.RUNNING)
                .values(status=JobStatus.PENDING, started_at=None)
            )
            db.commit()
            pending_ids = (
                db.execute(select(Job.id).where(Job.status == JobStatus.PENDING).order_by(Job.id))
                .scalars()
                .all()
            )
        for jid in pending_ids:
            self._queue.put_nowait(jid)

        for i in range(self.concurrency):
            self._workers.append(asyncio.create_task(self._worker_loop(i), name=f"jobworker-{i}"))
        log.info("JobQueue started: %d worker(s), %d pending", self.concurrency, len(pending_ids))

    async def stop(self) -> None:
        self._stopping = True
        for _ in self._workers:
            self._queue.put_nowait(-1)  # sentinel
        for w in self._workers:
            try:
                await asyncio.wait_for(w, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                w.cancel()
        self._workers.clear()
        log.info("JobQueue stopped")

    def enqueue(self, kind: JobKind, paper_id: Optional[int]) -> int:
        with SessionLocal() as db:
            job = Job(kind=kind, paper_id=paper_id, status=JobStatus.PENDING)
            db.add(job)
            db.commit()
            jid = job.id
        self._queue.put_nowait(jid)
        return jid

    async def _worker_loop(self, idx: int) -> None:
        while not self._stopping:
            jid = await self._queue.get()
            if jid == -1:
                return
            await self._run_one(jid)

    async def _run_one(self, jid: int) -> None:
        with SessionLocal() as db:
            job = db.get(Job, jid)
            if job is None:
                return
            if job.status not in (JobStatus.PENDING,):
                return
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.commit()
            kind: JobKind = job.kind  # SAEnum -> python value
            paper_id = job.paper_id

        handler = HANDLERS.get(kind)
        if handler is None:
            with SessionLocal() as db:
                job = db.get(Job, jid)
                if job:
                    job.status = JobStatus.FAILED
                    job.error = f"no handler for kind={kind}"
                    job.finished_at = datetime.utcnow()
                    db.commit()
            return

        if paper_id is None:
            with SessionLocal() as db:
                job = db.get(Job, jid)
                if job:
                    job.status = JobStatus.FAILED
                    job.error = "missing paper_id"
                    job.finished_at = datetime.utcnow()
                    db.commit()
            return

        err: Optional[str] = None
        try:
            with SessionLocal() as db:
                await handler(db, paper_id)
        except Exception as e:
            log.exception("job %s (%s) failed: %s", jid, kind, e)
            err = f"{type(e).__name__}: {e}"

        with SessionLocal() as db:
            job = db.get(Job, jid)
            if job:
                job.status = JobStatus.FAILED if err else JobStatus.DONE
                job.error = err
                job.finished_at = datetime.utcnow()
                db.commit()


# Singleton (initialised by lifespan)
_queue: Optional[JobQueue] = None


def init_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue(concurrency=settings.WORKER_CONCURRENCY)
    return _queue


def get_queue() -> JobQueue:
    if _queue is None:
        raise RuntimeError("Job queue not initialized")
    return _queue


def enqueue_light_for_new_paper(paper_id: int) -> None:
    q = get_queue()
    q.enqueue(JobKind.TRANSLATE, paper_id)
    q.enqueue(JobKind.TAG, paper_id)


def enqueue_heavy_for_to_read(paper_id: int) -> None:
    q = get_queue()
    q.enqueue(JobKind.SUMMARY, paper_id)
    q.enqueue(JobKind.FIGURES, paper_id)
