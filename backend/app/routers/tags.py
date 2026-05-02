from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PaperTag, Tag
from ..schemas import TagIn, TagOut, TagPatch

router = APIRouter(prefix="/tags", tags=["tags"])


def _normalize_tag_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _normalize_description(description: str | None) -> str | None:
    if description is None:
        return None
    description = description.strip()
    return description or None


def _ensure_unique_name(db: Session, name: str, tag_id: int | None = None) -> None:
    existing = db.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
    if existing is not None and existing.id != tag_id:
        raise HTTPException(409, f'tag "{name}" already exists')


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


@router.post("", response_model=TagOut)
def create_tag(payload: TagIn, db: Session = Depends(get_db)):
    name = _normalize_tag_name(payload.name)
    if not name:
        raise HTTPException(400, "tag name cannot be empty")
    _ensure_unique_name(db, name)

    tag = Tag(name=name, description=_normalize_description(payload.description))
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404)
    db.delete(tag)
    db.commit()
    return {"ok": True}


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: TagPatch, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404)

    if "name" in payload.model_fields_set:
        name = _normalize_tag_name(payload.name or "")
        if not name:
            raise HTTPException(400, "tag name cannot be empty")
        _ensure_unique_name(db, name, tag.id)
        tag.name = name

    if "description" in payload.model_fields_set:
        tag.description = _normalize_description(payload.description)

    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag
