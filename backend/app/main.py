from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import jobs as jobs_router
from .routers import papers as papers_router
from .routers import settings as settings_router
from .routers import subscriptions as subs_router
from .routers import tags as tags_router
from .workers.queue import init_queue
from .workers.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    queue = init_queue()
    await queue.start()
    await start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler()
        await queue.stop()


app = FastAPI(title="arXiv Daily Reader", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers_router.router, prefix="/api")
app.include_router(subs_router.router, prefix="/api")
app.include_router(tags_router.router, prefix="/api")
app.include_router(jobs_router.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")

# Serve extracted figures directly (faster than going through Python).
app.mount(
    "/figures",
    StaticFiles(directory=str(settings.figures_dir)),
    name="figures",
)


@app.get("/api/health")
def health():
    return {"ok": True, "model": settings.LLM_MODEL}
