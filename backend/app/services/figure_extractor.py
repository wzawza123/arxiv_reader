from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Figure, Paper

log = logging.getLogger(__name__)


def _download_pdf(arxiv_id: str, pdf_url: str) -> Path:
    safe_id = arxiv_id.replace("/", "_")
    out = settings.pdfs_dir / f"{safe_id}.pdf"
    if out.exists() and out.stat().st_size > 0:
        return out
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        with client.stream("GET", pdf_url) as resp:
            resp.raise_for_status()
            with open(out, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
    return out


def _docling_extract(pdf_path: Path, out_dir: Path) -> list[tuple[int, Path, str | None]]:
    """Run Docling and dump every PictureItem to ``out_dir/fig_<idx>.png``.

    Returns list of (idx, relative_path, caption).
    """
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipe_opts = PdfPipelineOptions()
    pipe_opts.images_scale = 2.0
    pipe_opts.generate_picture_images = True

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipe_opts)
        }
    )
    result = converter.convert(str(pdf_path))
    doc = result.document

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[tuple[int, Path, str | None]] = []
    pictures = getattr(doc, "pictures", []) or []
    for i, pic in enumerate(pictures):
        try:
            img = pic.get_image(doc)
        except Exception as e:
            log.warning("get_image failed for picture %d: %s", i, e)
            continue
        if img is None:
            continue
        fp = out_dir / f"fig_{i}.png"
        try:
            img.save(fp)
        except Exception as e:
            log.warning("save image failed for picture %d: %s", i, e)
            continue
        caption: str | None = None
        try:
            cap_fn = getattr(pic, "caption_text", None)
            if callable(cap_fn):
                caption = cap_fn(doc) or None
        except Exception:
            caption = None
        saved.append((i, fp, caption))
    return saved


async def extract_figures(db: Session, paper_id: int) -> None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return

    safe_id = paper.arxiv_id.replace("/", "_")
    out_dir = settings.figures_dir / safe_id

    def work() -> list[tuple[int, Path, str | None]]:
        pdf_path = _download_pdf(paper.arxiv_id, paper.pdf_url)
        return _docling_extract(pdf_path, out_dir)

    saved = await asyncio.to_thread(work)

    # Replace existing figure rows
    for old in list(paper.figures):
        db.delete(old)
    db.flush()

    base = settings.figures_dir
    for idx, abs_path, caption in saved:
        try:
            rel = abs_path.relative_to(base)
        except ValueError:
            rel = Path(safe_id) / abs_path.name
        db.add(
            Figure(
                paper_id=paper.id,
                idx=idx,
                path=str(rel).replace("\\", "/"),
                caption=caption,
            )
        )
    db.commit()
