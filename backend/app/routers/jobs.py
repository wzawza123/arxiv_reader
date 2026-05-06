from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Job, JobKind, JobStatus
from ..schemas import JobOut, FetchTriggerOut
from ..workers.queue import get_queue

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


@router.post("/fetch", response_model=FetchTriggerOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_fetch():
    job_id = get_queue().enqueue(JobKind.FETCH, None)
    return FetchTriggerOut(job_id=job_id, queued=1, new_papers=0)
