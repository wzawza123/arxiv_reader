from __future__ import annotations

import json
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Paper, Tag
from .nvidia_llm import chat_complete, load_prompt


def _tag_library_for_prompt(db: Session) -> str:
    tags = db.execute(select(Tag).order_by(Tag.name)).scalars().all()
    return json.dumps(
        [{"name": t.name, "description": t.description or ""} for t in tags],
        ensure_ascii=False,
    )


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    text = text.strip()
    # strip markdown fences if any
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(text)
        if m:
            return json.loads(m.group(0))
        raise


def _normalize_tag_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    return name


def _upsert_tags(db: Session, names: Iterable[str], descriptions: dict[str, str] | None = None) -> list[Tag]:
    descriptions = descriptions or {}
    out: list[Tag] = []
    for raw in names:
        name = _normalize_tag_name(raw)
        if not name:
            continue
        tag = db.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name, description=descriptions.get(name) or descriptions.get(raw))
            db.add(tag)
            db.flush()
        out.append(tag)
    return out


async def auto_tag(db: Session, paper_id: int) -> None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return

    prompt = load_prompt("tag.md").format(
        tag_library=_tag_library_for_prompt(db),
        title=paper.title.strip(),
        abstract=paper.abstract.strip(),
    )
    raw = await chat_complete(prompt, max_tokens=512)
    try:
        data = _extract_json(raw)
    except Exception:
        return

    selected = [str(x) for x in data.get("selected", []) if isinstance(x, str)]
    new_items = data.get("new", []) or []
    new_names = []
    descriptions: dict[str, str] = {}
    for item in new_items:
        if not isinstance(item, dict):
            continue
        nm = item.get("name")
        if not isinstance(nm, str):
            continue
        new_names.append(nm)
        desc = item.get("description")
        if isinstance(desc, str):
            descriptions[_normalize_tag_name(nm)] = desc

    all_names = selected + new_names
    tags = _upsert_tags(db, all_names, descriptions)

    # replace the paper's tags with the new set
    paper.tags = tags
    db.add(paper)
    db.commit()
