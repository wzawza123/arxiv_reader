from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import FetchSettingsIn, FetchSettingsOut
from ..services.app_settings import (
    DEFAULT_AUTO_FETCH_ENABLED,
    DEFAULT_HEAVY_PROCESSING_TRIGGER,
    default_fetch_time,
    get_auto_fetch_enabled,
    get_fetch_lookback_days,
    get_fetch_time,
    get_heavy_processing_trigger,
    set_auto_fetch_enabled,
    set_fetch_lookback_days,
    set_fetch_time,
    set_heavy_processing_trigger,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _server_time_payload() -> tuple[datetime, str, int]:
    now = datetime.now().astimezone()
    offset = now.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    return now, now.tzname() or "local", offset_minutes


def _fetch_settings_out(db: Session) -> FetchSettingsOut:
    server_time, server_timezone, server_utc_offset_minutes = _server_time_payload()
    return FetchSettingsOut(
        fetch_lookback_days=get_fetch_lookback_days(db),
        default_fetch_lookback_days=settings.FETCH_LOOKBACK_DAYS,
        auto_fetch_enabled=get_auto_fetch_enabled(db),
        default_auto_fetch_enabled=DEFAULT_AUTO_FETCH_ENABLED,
        fetch_time=get_fetch_time(db),
        default_fetch_time=default_fetch_time(),
        server_time=server_time,
        server_timezone=server_timezone,
        server_utc_offset_minutes=server_utc_offset_minutes,
        heavy_processing_trigger=get_heavy_processing_trigger(db),
        default_heavy_processing_trigger=DEFAULT_HEAVY_PROCESSING_TRIGGER,
    )


@router.get("/fetch", response_model=FetchSettingsOut)
def get_fetch_settings(db: Session = Depends(get_db)):
    return _fetch_settings_out(db)


@router.patch("/fetch", response_model=FetchSettingsOut)
def update_fetch_settings(payload: FetchSettingsIn, db: Session = Depends(get_db)):
    should_reload_scheduler = False
    if payload.fetch_lookback_days is not None:
        set_fetch_lookback_days(db, payload.fetch_lookback_days)
    if payload.auto_fetch_enabled is not None:
        set_auto_fetch_enabled(db, payload.auto_fetch_enabled)
        should_reload_scheduler = True
    if payload.fetch_time is not None:
        set_fetch_time(db, payload.fetch_time)
        should_reload_scheduler = True
    if payload.heavy_processing_trigger is not None:
        set_heavy_processing_trigger(db, payload.heavy_processing_trigger)
    if should_reload_scheduler:
        from ..workers.scheduler import reload_scheduler

        reload_scheduler()
    return _fetch_settings_out(db)
