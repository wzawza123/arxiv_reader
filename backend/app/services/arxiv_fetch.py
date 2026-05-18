from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

import arxiv
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Paper, PaperStatus, Subscription, SubscriptionKind
from .app_settings import get_fetch_lookback_days

_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")

log = logging.getLogger(__name__)


def _normalize_category(category: str) -> str:
    category = category.strip()
    if "." not in category:
        return category
    major, minor = category.split(".", 1)
    return f"{major.lower()}.{minor.upper()}"


def _fetch_category_allowlist() -> tuple[str, ...]:
    raw = settings.FETCH_CATEGORY_ALLOWLIST.strip()
    if not raw:
        return ()

    categories: list[str] = []
    seen: set[str] = set()
    for item in raw.replace(";", ",").split(","):
        category = _normalize_category(item)
        if not category:
            continue
        key = category.lower()
        if key in seen:
            continue
        categories.append(category)
        seen.add(key)
    return tuple(categories)


def _fetch_category_prefix() -> str:
    return settings.FETCH_CATEGORY_PREFIX.strip()


def _category_scope_query() -> str:
    allowlist = _fetch_category_allowlist()
    if allowlist:
        return "(" + " OR ".join(f"cat:{category}" for category in allowlist) + ")"

    prefix = _fetch_category_prefix()
    if not prefix:
        return ""
    if prefix.endswith("."):
        category = f"{prefix}*"
    elif "." not in prefix:
        category = f"{prefix}.*"
    else:
        category = prefix
    return f"cat:{category}"


def _has_category_in_scope(categories: Iterable[str]) -> bool:
    allowlist = _fetch_category_allowlist()
    if allowlist:
        allowed = {category.lower() for category in allowlist}
        return any(_normalize_category(c).lower() in allowed for c in categories)

    prefix = _fetch_category_prefix()
    if not prefix:
        return True
    prefix = prefix.lower()
    return any(c.lower().startswith(prefix) for c in categories)


def _build_query(sub: Subscription) -> str:
    scope_query = _category_scope_query()
    if sub.kind == SubscriptionKind.CATEGORY:
        category_query = f"cat:{sub.value}"
        if not scope_query or _has_category_in_scope([sub.value]):
            return category_query
        return f"({scope_query}) AND {category_query}"
    # keyword: search title + abstract
    val = sub.value.replace('"', '')
    keyword_query = f'all:"{val}"'
    if scope_query:
        return f"({scope_query}) AND {keyword_query}"
    return keyword_query


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


def _paper_to_dict(r: arxiv.Result) -> dict:
    arxiv_id = _normalize_arxiv_id(r.entry_id)
    return {
        "arxiv_id": arxiv_id,
        "title": (r.title or "").strip().replace("\n", " "),
        "authors": [a.name for a in (r.authors or [])],
        "abstract": (r.summary or "").strip(),
        "categories": list(r.categories or []),
        "pdf_url": r.pdf_url or "",
        "abs_url": r.entry_id,
        "published_at": _to_naive_utc(r.published).isoformat(),
    }


def search_arxiv_by_query(query: str, max_results: int = 20) -> list[dict]:
    """Search arXiv by title keyword or bare arXiv ID; returns candidates without saving."""
    query = query.strip()
    client = arxiv.Client(page_size=min(max_results, 100), delay_seconds=3.0, num_retries=3)

    if _ARXIV_ID_RE.match(query):
        bare_id = _normalize_arxiv_id(query)
        search = arxiv.Search(id_list=[bare_id], max_results=1)
    else:
        safe_q = query.replace('"', "")
        arxiv_query = f'ti:"{safe_q}"'
        search = arxiv.Search(
            query=arxiv_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )

    return [_paper_to_dict(r) for r in client.results(search)]


def import_arxiv_papers(db: Session, arxiv_ids: list[str]) -> tuple[list[int], list[str]]:
    """Fetch specific papers from arXiv by ID and insert into DB.

    Returns (new_paper_ids, already_existing_arxiv_ids).
    """
    normalized = [_normalize_arxiv_id(aid) for aid in arxiv_ids]

    existing_ids: set[str] = set(
        db.execute(select(Paper.arxiv_id).where(Paper.arxiv_id.in_(normalized))).scalars().all()
    )
    to_fetch = [aid for aid in normalized if aid not in existing_ids]
    skipped = list(existing_ids)

    if not to_fetch:
        return [], skipped

    client = arxiv.Client(page_size=len(to_fetch), delay_seconds=1.0, num_retries=3)
    search = arxiv.Search(id_list=to_fetch, max_results=len(to_fetch))

    to_fetch_set = set(to_fetch)
    new_ids: list[int] = []
    for r in client.results(search):
        arxiv_id = _normalize_arxiv_id(r.entry_id)
        if arxiv_id not in to_fetch_set:
            continue
        paper = Paper(
            arxiv_id=arxiv_id,
            title=(r.title or "").strip().replace("\n", " "),
            authors=[a.name for a in (r.authors or [])],
            abstract=(r.summary or "").strip(),
            categories=list(r.categories or []),
            pdf_url=r.pdf_url or "",
            abs_url=r.entry_id,
            published_at=_to_naive_utc(r.published),
            status=PaperStatus.NEW,
        )
        db.add(paper)
        db.flush()
        new_ids.append(paper.id)

    db.commit()
    return new_ids, skipped


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
            categories = list(r.categories or [])
            if not _has_category_in_scope(categories):
                continue

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
                categories=categories,
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
