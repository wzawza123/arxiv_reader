from __future__ import annotations

import re
import threading
from pathlib import Path

import httpx

from ..config import settings

_LOCKS: dict[Path, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_SPACES_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def pdf_path_for(arxiv_id: str) -> Path:
    safe_id = arxiv_id.replace("/", "_")
    return settings.pdfs_dir / f"{safe_id}.pdf"


def _lock_for(path: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(path)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[path] = lock
        return lock


def download_pdf(arxiv_id: str, pdf_url: str) -> Path:
    out = pdf_path_for(arxiv_id)
    if out.exists() and out.stat().st_size > 0:
        return out

    with _lock_for(out):
        if out.exists() and out.stat().st_size > 0:
            return out

        tmp = out.with_suffix(out.suffix + ".tmp")
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", pdf_url) as resp:
                    resp.raise_for_status()
                    with open(tmp, "wb") as f:
                        for chunk in resp.iter_bytes():
                            f.write(chunk)

            if not tmp.exists() or tmp.stat().st_size == 0:
                raise RuntimeError(f"downloaded empty PDF for {arxiv_id}")

            tmp.replace(out)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    return out


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_SPACES_RE.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _truncate_middle(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text

    head_len = max_chars * 3 // 4
    tail_len = max_chars - head_len
    omitted = len(text) - head_len - tail_len
    return (
        text[:head_len].rstrip()
        + f"\n\n[... middle {omitted} characters omitted due to context limit ...]\n\n"
        + text[-tail_len:].lstrip()
    )


def extract_pdf_text(pdf_path: Path, *, max_chars: int) -> str:
    from docling.document_converter import DocumentConverter

    result = DocumentConverter().convert(str(pdf_path))
    doc = result.document

    text = ""
    for method_name in ("export_to_markdown", "export_to_text"):
        method = getattr(doc, method_name, None)
        if callable(method):
            text = method() or ""
            if text.strip():
                break

    if not text.strip():
        text = str(doc)

    text = _normalize_text(text)
    if not text:
        raise RuntimeError(f"no text extracted from PDF: {pdf_path}")

    return _truncate_middle(text, max_chars)
