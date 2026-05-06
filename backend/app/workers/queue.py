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
from ..services.pdfs import delete_downloaded_pdf

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

PDF_JOB_KINDS = {JobKind.SUMMARY, JobKind.FIGURES}


def _delete_downloaded_pdf_safely(arxiv_id: str) -> None:
    try:
        delete_downloaded_pdf(arxiv_id)
    except OSError as e:
        log.warning("failed to delete downloaded PDF for %s: %s", arxiv_id, e)


class JobQueue:
    def __init__(self, concurrency: int) -> None:
        self.concurrency = concurrency
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
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
        self._enqueue_id(jid)
        return jid

    def _enqueue_id(self, jid: int) -> None:
        if self._loop is None or self._loop.is_closed():
            self._queue.put_nowait(jid)
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self._loop:
            self._queue.put_nowait(jid)
        else:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, jid)

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

        if kind == JobKind.FETCH:
            err: Optional[str] = None
            try:
                from . import scheduler as scheduler_mod

                new_count, queued = await asyncio.to_thread(scheduler_mod.run_fetch_now)
                log.info("fetch job %s completed: %d new paper(s), %d queued job(s)", jid, new_count, queued)
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
            return

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

        if kind in PDF_JOB_KINDS:
            with SessionLocal() as db:
                paper = db.get(Paper, paper_id)
                if paper is not None and paper.status == PaperStatus.NOT_INTERESTED:
                    _delete_downloaded_pdf_safely(paper.arxiv_id)
                    job = db.get(Job, jid)
                    if job:
                        job.status = JobStatus.DONE
                        job.error = None
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
            paper = db.get(Paper, paper_id)
            if kind in PDF_JOB_KINDS and paper is not None and paper.status == PaperStatus.NOT_INTERESTED:
                _delete_downloaded_pdf_safely(paper.arxiv_id)
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


def _has_job_with_status(db: Session, paper_id: int, kind: JobKind, statuses: set[JobStatus]) -> bool:
    return (
        db.execute(
            select(Job.id)
            .where(
                Job.paper_id == paper_id,
                Job.kind == kind,
                Job.status.in_(statuses),
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def enqueue_missing_heavy_for_to_read(paper_id: int) -> int:
    """Queue missing heavy work without duplicating completed or active jobs."""
    q = get_queue()
    satisfied_statuses = {JobStatus.DONE, JobStatus.PENDING, JobStatus.RUNNING}
    with SessionLocal() as db:
        missing = [
            kind
            for kind in (JobKind.SUMMARY, JobKind.FIGURES)
            if not _has_job_with_status(db, paper_id, kind, satisfied_statuses)
        ]
    for kind in missing:
        q.enqueue(kind, paper_id)
    return len(missing)
