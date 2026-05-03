from __future__ import annotations

import asyncio
import re
from collections.abc import Callable

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


_LIST_ITEM_RE = re.compile(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_TOP_LEVEL_ITEM_RE = re.compile(r"(?m)^(?:[-*+]\s+|\d+[.)]\s+)")
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)


def _check_min_content(text: str, label: str, min_chars: int) -> None:
    stripped = text.strip()
    if len(stripped) < min_chars:
        raise ValueError(f"{label} is too short: {len(stripped)} chars")
    if stripped.count("```") % 2:
        raise ValueError(f"{label} has an unclosed markdown fence")


def _validate_problem_summary(text: str) -> None:
    _check_min_content(text, "problem summary", 160)
    if len(_LIST_ITEM_RE.findall(text)) < 1 and "问题" not in text:
        raise ValueError("problem summary does not contain any problem item")


def _validate_insights_table(text: str) -> None:
    _check_min_content(text, "insights table", 240)
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines or not lines[0].startswith("|"):
        raise ValueError("insights output must start with a markdown table")

    header_idx = next(
        (
            idx
            for idx, line in enumerate(lines)
            if _TABLE_ROW_RE.match(line)
            and "主题" in line
            and "内容" in line
            and "出处" in line
        ),
        None,
    )
    if header_idx is None:
        raise ValueError("insights table is missing required columns")
    if header_idx + 1 >= len(lines) or not _TABLE_SEPARATOR_RE.match(lines[header_idx + 1]):
        raise ValueError("insights table is missing the markdown separator row")

    table_rows = [line for line in lines[header_idx + 2 :] if _TABLE_ROW_RE.match(line)]
    if len(table_rows) < 3:
        raise ValueError(f"insights table has too few data rows: {len(table_rows)}")


def _validate_followup(text: str) -> None:
    _check_min_content(text, "follow-up summary", 240)
    item_count = len(_TOP_LEVEL_ITEM_RE.findall(text))
    if item_count < 3:
        raise ValueError(f"follow-up summary has too few top-level items: {item_count}")
    if item_count > 5:
        raise ValueError(f"follow-up summary has too many top-level items: {item_count}")
    if "方案" not in text:
        raise ValueError("follow-up summary is missing solution sections")
    if "风险" not in text and "难点" not in text:
        raise ValueError("follow-up summary is missing risk or difficulty sections")


async def _chat_summary_part(
    prompt: str,
    *,
    validators: list[Callable[[str], None]],
    max_tokens: int | None = None,
) -> str:
    return await chat_complete(
        prompt,
        max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
        retry_max_tokens=settings.LLM_RETRY_MAX_TOKENS,
        validators=validators,
    )


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

    problems = await _chat_summary_part(
        load_prompt("summarize_problem.md").format(context=context),
        validators=[_validate_problem_summary],
    )
    _save_summary_part(db, paper, "summary_md", problems)

    insights = await _chat_summary_part(
        load_prompt("summarize_insights.md").format(
            context=context,
            problems=problems.strip(),
        ),
        validators=[_validate_insights_table],
    )
    _save_summary_part(db, paper, "insights_md", insights)

    followup = await _chat_summary_part(
        load_prompt("summarize_followup.md").format(
            context=context,
            problems=problems.strip(),
            insights=insights.strip(),
        ),
        validators=[_validate_followup],
    )
    _save_summary_part(db, paper, "followup_md", followup)
