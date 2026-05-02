from __future__ import annotations

import re
from sqlalchemy.orm import Session

from ..models import Paper
from .nvidia_llm import chat_complete, load_prompt


_SECTION_RE = re.compile(r"^##\s+\d+\.\s*", re.MULTILINE)


def _split_sections(md: str) -> tuple[str, str, str]:
    """Split LLM output into three sections by H2 headers '## 1.', '## 2.', '## 3.'.

    Returns (problems, insights, followup) — any missing section returns "".
    """
    md = md.strip()
    parts = _SECTION_RE.split(md)
    headers = _SECTION_RE.findall(md)
    sections: dict[int, str] = {}
    # parts[0] is preamble before first header (often empty)
    for header, body in zip(headers, parts[1:]):
        m = re.match(r"^##\s+(\d+)\.", header)
        if not m:
            continue
        idx = int(m.group(1))
        sections[idx] = body.strip()
    return sections.get(1, ""), sections.get(2, ""), sections.get(3, "")


async def summarize(db: Session, paper_id: int, body_excerpt: str = "") -> None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return

    prompt = load_prompt("summarize.md").format(
        title=paper.title.strip(),
        abstract=paper.abstract.strip(),
        body_excerpt=body_excerpt or "（无）",
    )
    raw = await chat_complete(prompt, max_tokens=4096)
    problems, insights, followup = _split_sections(raw)

    # Fallback: if the splitter found nothing, dump everything into summary_md.
    if not (problems or insights or followup):
        paper.summary_md = raw.strip()
    else:
        paper.summary_md = problems
        paper.insights_md = insights
        paper.followup_md = followup
    db.add(paper)
    db.commit()
