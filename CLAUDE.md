# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

arXiv Daily Reader is a single-machine local tool that automatically fetches arXiv papers, translates abstracts to Chinese, auto-tags them, and generates structured reading summaries via an LLM (NVIDIA NIM). Papers flow through four states: **new → to_read → read / not_interested**.

## Commands

### Backend

The backend Python environment is the conda env at `/opt/data/private/envs/agent`. Always use its binaries explicitly — do not rely on system Python or an activated conda env.

```bash
# Install/update deps
/opt/data/private/envs/agent/bin/pip install -r backend/requirements.txt

# Start backend (from repo root or backend/)
cd backend && /opt/data/private/envs/agent/bin/uvicorn app.main:app --reload --port 8000

# Health check
curl http://127.0.0.1:8000/api/health

# Run all tests
cd backend && /opt/data/private/envs/agent/bin/python -m pytest

# Run a single test file
cd backend && /opt/data/private/envs/agent/bin/python -m pytest tests/test_summarizer_validation.py -v
```

### Frontend

```bash
cd frontend && npm install
cd frontend && npm run dev          # dev server on :5173, proxies /api and /figures to :8000
cd frontend && npm run build        # output to frontend/dist/
```

## Architecture

### Backend (FastAPI + SQLite + APScheduler)

`backend/app/main.py` — FastAPI lifespan wires together three subsystems at startup:
1. `db.init_db()` — SQLAlchemy `create_all` against the SQLite DB
2. `workers/queue.py::init_queue()` — asyncio-based `JobQueue` singleton; re-enqueues any `running` jobs (reset to `pending`) and all existing `pending` jobs
3. `workers/scheduler.py::start_scheduler()` — APScheduler daily cron for auto-fetch

**Data models** (`models.py`):
- `Paper` — central entity; has `status` (new/to_read/not_interested/read), `abstract_zh`, three summary markdown columns (`summary_md`, `insights_md`, `followup_md`), and relationships to `Tag` (M2M via `PaperTag`) and `Figure`
- `Job` — every background task (translate/tag/summary/figures/fetch) is a persistent DB row with `status` (pending/running/done/failed)
- `AppSetting` — key/value store for runtime-configurable settings (fetch time, lookback days, heavy processing trigger)

**Job pipeline** (`workers/queue.py`):

Light jobs (enqueued for every new paper):
- `TRANSLATE` → `services/translator.py` — calls LLM to translate abstract to Chinese
- `TAG` → `services/tagger.py` — LLM auto-creates and assigns tags

Heavy jobs (enqueued when paper is marked `to_read`, or optionally at fetch time):
- `SUMMARY` → `services/summarizer.py` — downloads PDF, extracts text, runs 3 sequential LLM prompts (problem/insights/followup), each validated before accepting
- `FIGURES` → `services/figure_extractor.py` — downloads PDF, runs Docling layout analysis, saves figures to `data/figures/`

**LLM client** (`services/nvidia_llm.py`): wraps the OpenAI-compatible NVIDIA NIM API. Includes retry logic with exponential backoff and token budget escalation on truncation.

**Prompts** (`app/prompts/`): Markdown template files — `translate.md`, `tag.md`, `summarize_problem.md`, `summarize_insights.md`, `summarize_followup.md`, `summarize_context.md`.

**Routers** (`routers/`): Standard FastAPI routers — `papers.py`, `subscriptions.py`, `tags.py`, `jobs.py`, `settings.py`. All mounted under `/api`.

**Settings** (`config.py`): Pydantic-settings loaded from `backend/.env`. Runtime-overridable settings (fetch schedule, lookback days, heavy processing trigger) are stored in the `app_settings` DB table via `services/app_settings.py` and take precedence over `.env` values.

### Frontend (React 18 + Vite + TypeScript + Tailwind)

- `src/api/client.ts` — all API types and axios calls. **This is the single source of truth for API shape.** All page/component API calls go through the typed functions here (`PaperApi`, `SubsApi`, `TagApi`, `JobApi`, `ArxivApi`, `SettingsApi`).
- `src/App.tsx` — React Router setup; sidebar nav with per-status paper counts from `PaperApi.counts()`.
- `src/pages/` — one file per route: Inbox (status=new), ToRead, Read, NotInterested, PaperDetail, Settings, Jobs, Search.
- `src/components/` — `PaperCard` (list item with status controls), `PaperListWithTagFilter` (shared list+filter shell), `MarkdownView` (react-markdown+remark-gfm), `TagBadge`.
- Data fetching uses `@tanstack/react-query`.

Vite proxies `/api` and `/figures` to the backend (`VITE_BACKEND_URL`, default `http://127.0.0.1:8000`). When running frontend and backend on separate public tunnels, set `VITE_API_BASE_URL` and `VITE_FIGURES_BASE_URL` in `frontend/.env`, and add the frontend origin to `CORS_ALLOW_ORIGINS` in `backend/.env`.

## Key Conventions

- `PATCH /api/papers/{id}` uses `POST` in the frontend client (the router accepts both; note `PaperApi.patch` calls `api.post`).
- PDF files are deleted after summary/figures jobs complete if the paper is `not_interested`, to save disk.
- The `JobQueue` is a module-level singleton accessed via `get_queue()`. Enqueue helpers: `enqueue_light_for_new_paper(paper_id)` and `enqueue_heavy_for_to_read(paper_id)`.
- `SUMMARY` jobs validate each of the three LLM responses with dedicated `_validate_*` functions in `summarizer.py` before accepting them; failed validation triggers a retry counted against `LLM_MAX_RETRIES`.
- `data/` (SQLite, PDFs, figures) is git-ignored; `backend/.env` is git-ignored.
