from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_, delete
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Figure, Job, Paper, PaperStatus, PaperTag, Tag, JobKind
from ..schemas import PaperListItem, PaperDetail, PaperNeighbors, PaperPatch, ArxivCandidate, ArxivImportIn, ArxivImportOut
from ..services.app_settings import (
    HEAVY_PROCESSING_ON_FETCH,
    HEAVY_PROCESSING_ON_TO_READ,
    get_heavy_processing_trigger,
)
from ..services.pdfs import delete_downloaded_pdf
from ..workers.queue import (
    enqueue_heavy_for_to_read,
    enqueue_light_for_new_paper,
    enqueue_missing_heavy_for_to_read,
    get_queue,
)

router = APIRouter(prefix="/papers", tags=["papers"])
log = logging.getLogger(__name__)


def _normalize_tag_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _apply_paper_filters(stmt, status: Optional[str], tag: Optional[str]):
    if status:
        try:
            stmt = stmt.where(Paper.status == PaperStatus(status))
        except ValueError:
            raise HTTPException(400, f"invalid status: {status}")
    if tag:
        stmt = stmt.join(Paper.tags).where(Tag.name == _normalize_tag_name(tag))
    return stmt


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
    stmt = _apply_paper_filters(stmt, status, tag)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Paper.title.ilike(like), Paper.abstract.ilike(like)))

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).unique().scalars().all()
    return rows


@router.delete("")
@router.post("/clear")
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


@router.get("/{paper_id}/neighbors", response_model=PaperNeighbors)
def get_paper_neighbors(
    paper_id: int,
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404)

    base_stmt = select(Paper).options(selectinload(Paper.tags))
    base_stmt = _apply_paper_filters(base_stmt, status, tag)

    previous_stmt = (
        base_stmt.where(
            or_(
                Paper.published_at > paper.published_at,
                and_(Paper.published_at == paper.published_at, Paper.id > paper.id),
            )
        )
        .order_by(Paper.published_at.asc(), Paper.id.asc())
        .limit(1)
    )
    next_stmt = (
        base_stmt.where(
            or_(
                Paper.published_at < paper.published_at,
                and_(Paper.published_at == paper.published_at, Paper.id < paper.id),
            )
        )
        .order_by(Paper.published_at.desc(), Paper.id.desc())
        .limit(1)
    )

    return {
        "previous": db.execute(previous_stmt).unique().scalar_one_or_none(),
        "next": db.execute(next_stmt).unique().scalar_one_or_none(),
    }


@router.patch("/{paper_id}", response_model=PaperDetail)
@router.post("/{paper_id}", response_model=PaperDetail)
def update_paper(paper_id: int, patch: PaperPatch, db: Session = Depends(get_db)):
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(404)

    trigger_heavy = False
    trigger_missing_heavy = False
    delete_local_pdf = False
    if patch.status is not None:
        new_status = PaperStatus(patch.status)
        moved_to_to_read = paper.status != PaperStatus.TO_READ and new_status == PaperStatus.TO_READ
        if moved_to_to_read:
            heavy_trigger = get_heavy_processing_trigger(db)
            if heavy_trigger == HEAVY_PROCESSING_ON_TO_READ:
                trigger_heavy = True
            elif heavy_trigger == HEAVY_PROCESSING_ON_FETCH:
                trigger_missing_heavy = True
        if new_status == PaperStatus.NOT_INTERESTED:
            delete_local_pdf = True
        paper.status = new_status

    if patch.tag_ids is not None:
        tags = db.execute(select(Tag).where(Tag.id.in_(patch.tag_ids))).scalars().all()
        paper.tags = list(tags)

    db.add(paper)
    db.commit()
    db.refresh(paper)

    if trigger_heavy:
        enqueue_heavy_for_to_read(paper.id)
    if trigger_missing_heavy:
        enqueue_missing_heavy_for_to_read(paper.id)
    if delete_local_pdf:
        try:
            delete_downloaded_pdf(paper.arxiv_id)
        except OSError as e:
            log.warning("failed to delete downloaded PDF for %s: %s", paper.arxiv_id, e)

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


@router.get("/arxiv/search", response_model=list[ArxivCandidate])
def search_arxiv(
    q: str = Query(..., min_length=1),
    max_results: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    import arxiv as arxiv_lib
    from ..services.arxiv_fetch import search_arxiv_by_query

    try:
        candidates = search_arxiv_by_query(q, max_results)
    except arxiv_lib.HTTPError as e:
        if e.status == 429:
            raise HTTPException(503, "arXiv API 请求频率限制，请稍等片刻后重试。")
        raise HTTPException(502, f"arXiv API 错误: HTTP {e.status}")
    except Exception as e:
        log.exception("arxiv search failed: %s", e)
        raise HTTPException(502, "arXiv 搜索失败，请稍后重试。")

    arxiv_ids = [c["arxiv_id"] for c in candidates]
    existing = {
        row[0]: row[1]
        for row in db.execute(
            select(Paper.arxiv_id, Paper.id).where(Paper.arxiv_id.in_(arxiv_ids))
        ).all()
    }
    for c in candidates:
        c["already_imported"] = c["arxiv_id"] in existing
        c["paper_id"] = existing.get(c["arxiv_id"])
    return candidates


@router.post("/arxiv/import", response_model=ArxivImportOut)
def import_arxiv(body: ArxivImportIn, db: Session = Depends(get_db)):
    import arxiv as arxiv_lib
    from ..services.arxiv_fetch import import_arxiv_papers

    try:
        new_ids, skipped = import_arxiv_papers(db, body.arxiv_ids)
    except arxiv_lib.HTTPError as e:
        if e.status == 429:
            raise HTTPException(503, "arXiv API 请求频率限制，请稍等片刻后重试。")
        raise HTTPException(502, f"arXiv API 错误: HTTP {e.status}")
    except Exception as e:
        log.exception("arxiv import failed: %s", e)
        raise HTTPException(502, "arXiv 导入失败，请稍后重试。")

    heavy_trigger = get_heavy_processing_trigger(db)
    for paper_id in new_ids:
        enqueue_light_for_new_paper(paper_id)
        if heavy_trigger == HEAVY_PROCESSING_ON_FETCH:
            enqueue_heavy_for_to_read(paper_id)
    return {"imported": new_ids, "skipped": skipped}


@router.get("/stats/counts")
def status_counts(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Paper.status, func.count(Paper.id)).group_by(Paper.status)
    ).all()
    out = {s.value: 0 for s in PaperStatus}
    for status, count in rows:
        out[status.value if hasattr(status, "value") else str(status)] = count
    return out
