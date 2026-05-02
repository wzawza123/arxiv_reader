from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

import arxiv
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Paper, PaperStatus, Subscription, SubscriptionKind
from .app_settings import get_fetch_lookback_days

log = logging.getLogger(__name__)


def _build_query(sub: Subscription) -> str:
    if sub.kind == SubscriptionKind.CATEGORY:
        return f"cat:{sub.value}"
    # keyword: search title + abstract
    val = sub.value.replace('"', '')
    return f'all:"{val}"'


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _normalize_arxiv_id(entry_id: str) -> str:
    # entry_id like "http://arxiv.org/abs/2401.12345v2"
    raw = entry_id.rsplit("/", 1)[-1]
    if "v" in raw:
        # strip version suffix
        head, _, tail = raw.rpartition("v")
        if tail.isdigit():
            raw = head
    return raw


def _search_one(sub: Subscription, max_results: int) -> Iterable[arxiv.Result]:
    client = arxiv.Client(
        page_size=min(max_results, 100),
        delay_seconds=3.0,
        num_retries=3,
    )
    search = arxiv.Search(
        query=_build_query(sub),
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    return client.results(search)


def fetch_subscriptions(db: Session) -> list[int]:
    """Run all enabled subscriptions; insert new Paper rows; return list of new paper IDs."""
    subs = db.execute(select(Subscription).where(Subscription.enabled.is_(True))).scalars().all()
    if not subs:
        return []

    cutoff = datetime.utcnow() - timedelta(days=get_fetch_lookback_days(db))
    new_ids: list[int] = []
    seen_arxiv_ids: set[str] = set()

    for sub in subs:
        try:
            results = list(_search_one(sub, settings.FETCH_MAX_RESULTS_PER_QUERY))
        except Exception as e:
            log.exception("fetch failed for subscription %s=%s: %s", sub.kind, sub.value, e)
            continue

        for r in results:
            arxiv_id = _normalize_arxiv_id(r.entry_id)
            if arxiv_id in seen_arxiv_ids:
                continue
            seen_arxiv_ids.add(arxiv_id)

            published = _to_naive_utc(r.published)
            if published < cutoff:
                continue

            existing = db.execute(
                select(Paper).where(Paper.arxiv_id == arxiv_id)
            ).scalar_one_or_none()
            if existing is not None:
                continue

            paper = Paper(
                arxiv_id=arxiv_id,
                title=(r.title or "").strip().replace("\n", " "),
                authors=[a.name for a in (r.authors or [])],
                abstract=(r.summary or "").strip(),
                categories=list(r.categories or []),
                pdf_url=r.pdf_url,
                abs_url=r.entry_id,
                published_at=published,
                status=PaperStatus.NEW,
            )
            db.add(paper)
            db.flush()
            new_ids.append(paper.id)

        sub.last_fetched_at = datetime.utcnow()
        db.add(sub)

    db.commit()
    return new_ids
