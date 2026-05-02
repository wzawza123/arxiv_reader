from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Paper
from .nvidia_llm import chat_complete, load_prompt


async def translate_abstract(db: Session, paper_id: int) -> None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return
    if paper.abstract_zh:
        return
    prompt = load_prompt("translate.md").format(abstract=paper.abstract.strip())
    zh = (await chat_complete(prompt)).strip()
    paper.abstract_zh = zh
    db.add(paper)
    db.commit()
