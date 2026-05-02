from __future__ import annotations

import asyncio
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Paper
from .nvidia_llm import chat_complete, load_prompt
from .pdfs import download_pdf, extract_pdf_text


def _load_pdf_excerpt(arxiv_id: str, pdf_url: str) -> str:
    pdf_path = download_pdf(arxiv_id, pdf_url)
    return extract_pdf_text(pdf_path, max_chars=settings.SUMMARY_PDF_MAX_CHARS)


def _paper_context(paper: Paper, body_excerpt: str) -> str:
    return load_prompt("summarize_context.md").format(
        title=paper.title.strip(),
        abstract=paper.abstract.strip(),
        body_excerpt=body_excerpt.strip(),
    )


def _save_summary_part(db: Session, paper: Paper, field: str, value: str) -> None:
    setattr(paper, field, value.strip())
    db.add(paper)
    db.commit()
    db.refresh(paper)


async def summarize(db: Session, paper_id: int, body_excerpt: str | None = None) -> None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return

    paper.summary_md = None
    paper.insights_md = None
    paper.followup_md = None
    db.add(paper)
    db.commit()

    if body_excerpt is None:
        body_excerpt = await asyncio.to_thread(
            _load_pdf_excerpt,
            paper.arxiv_id,
            paper.pdf_url,
        )

    context = _paper_context(paper, body_excerpt)

    problems = await chat_complete(
        load_prompt("summarize_problem.md").format(context=context),
        max_tokens=2048,
    )
    _save_summary_part(db, paper, "summary_md", problems)

    insights = await chat_complete(
        load_prompt("summarize_insights.md").format(
            context=context,
            problems=problems.strip(),
        ),
        max_tokens=4096,
    )
    _save_summary_part(db, paper, "insights_md", insights)

    followup = await chat_complete(
        load_prompt("summarize_followup.md").format(
            context=context,
            problems=problems.strip(),
            insights=insights.strip(),
        ),
        max_tokens=4096,
    )
    _save_summary_part(db, paper, "followup_md", followup)
