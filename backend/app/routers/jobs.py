from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Job, JobStatus
from ..schemas import JobOut, FetchTriggerOut
from ..workers import scheduler as scheduler_mod

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Job).order_by(Job.id.desc()).limit(limit)
    if status:
        try:
            stmt = stmt.where(Job.status == JobStatus(status))
        except ValueError:
            pass
    return db.execute(stmt).scalars().all()


@router.post("/fetch", response_model=FetchTriggerOut)
async def trigger_fetch(background: BackgroundTasks):
    # Run fetch in a background task so the request returns quickly.
    new_count, queued = await _run_fetch_async()
    return FetchTriggerOut(queued=queued, new_papers=new_count)


async def _run_fetch_async() -> tuple[int, int]:
    import asyncio
    return await asyncio.to_thread(scheduler_mod.run_fetch_now)
