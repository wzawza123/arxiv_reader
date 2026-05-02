from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PaperTag, Tag
from ..schemas import TagOut

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[dict])
def list_tags(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Tag, func.count(PaperTag.paper_id))
        .outerjoin(PaperTag, PaperTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    ).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "paper_count": cnt,
        }
        for t, cnt in rows
    ]


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404)
    db.delete(tag)
    db.commit()
    return {"ok": True}


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: dict, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404)
    if "name" in payload and payload["name"]:
        tag.name = str(payload["name"]).strip().lower()
    if "description" in payload:
        tag.description = payload["description"]
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
