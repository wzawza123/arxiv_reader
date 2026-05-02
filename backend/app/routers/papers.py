from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Figure, Job, Paper, PaperStatus, PaperTag, Tag, JobKind
from ..schemas import PaperListItem, PaperDetail, PaperPatch
from ..workers.queue import get_queue, enqueue_heavy_for_to_read

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=list[PaperListItem])
def list_papers(
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Paper).options(selectinload(Paper.tags)).order_by(Paper.published_at.desc())
    if status:
        try:
            stmt = stmt.where(Paper.status == PaperStatus(status))
        except ValueError:
            raise HTTPException(400, f"invalid status: {status}")
    if tag:
        stmt = stmt.join(Paper.tags).where(Tag.name == tag.lower().strip())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Paper.title.ilike(like), Paper.abstract.ilike(like)))

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).unique().scalars().all()
    return rows


@router.delete("")
def delete_all_papers(db: Session = Depends(get_db)):
    paper_count = db.scalar(select(func.count(Paper.id))) or 0
    db.execute(delete(Job).where(Job.paper_id.is_not(None)))
    db.execute(delete(Figure))
    db.execute(delete(PaperTag))
    db.execute(delete(Paper))
    db.commit()
    return {"deleted": paper_count}


@router.get("/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404)
    return paper


@router.patch("/{paper_id}", response_model=PaperDetail)
def update_paper(paper_id: int, patch: PaperPatch, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404)

    trigger_heavy = False
    if patch.status is not None:
        new_status = PaperStatus(patch.status)
        if paper.status != PaperStatus.TO_READ and new_status == PaperStatus.TO_READ:
            trigger_heavy = True
        paper.status = new_status

    if patch.tag_ids is not None:
        tags = db.execute(select(Tag).where(Tag.id.in_(patch.tag_ids))).scalars().all()
        paper.tags = list(tags)

    db.add(paper)
    db.commit()
    db.refresh(paper)

    if trigger_heavy:
        enqueue_heavy_for_to_read(paper.id)

    return paper


@router.post("/{paper_id}/reprocess")
def reprocess_paper(
    paper_id: int,
    stage: str = Query(..., pattern="^(translate|tag|summary|figures)$"),
    db: Session = Depends(get_db),
):
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404)
    q = get_queue()
    kind_map = {
        "translate": JobKind.TRANSLATE,
        "tag": JobKind.TAG,
        "summary": JobKind.SUMMARY,
        "figures": JobKind.FIGURES,
    }
    job_id = q.enqueue(kind_map[stage], paper.id)
    return {"job_id": job_id}


@router.get("/stats/counts")
def status_counts(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Paper.status, func.count(Paper.id)).group_by(Paper.status)
    ).all()
    out = {s.value: 0 for s in PaperStatus}
    for status, count in rows:
        out[status.value if hasattr(status, "value") else str(status)] = count
    return out
