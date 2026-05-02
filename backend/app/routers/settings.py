from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import FetchSettingsIn, FetchSettingsOut
from ..services.app_settings import (
    DEFAULT_HEAVY_PROCESSING_TRIGGER,
    get_fetch_lookback_days,
    get_heavy_processing_trigger,
    set_fetch_lookback_days,
    set_heavy_processing_trigger,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/fetch", response_model=FetchSettingsOut)
def get_fetch_settings(db: Session = Depends(get_db)):
    return FetchSettingsOut(
        fetch_lookback_days=get_fetch_lookback_days(db),
        default_fetch_lookback_days=settings.FETCH_LOOKBACK_DAYS,
        heavy_processing_trigger=get_heavy_processing_trigger(db),
        default_heavy_processing_trigger=DEFAULT_HEAVY_PROCESSING_TRIGGER,
    )


@router.patch("/fetch", response_model=FetchSettingsOut)
def update_fetch_settings(payload: FetchSettingsIn, db: Session = Depends(get_db)):
    if payload.fetch_lookback_days is not None:
        set_fetch_lookback_days(db, payload.fetch_lookback_days)
    if payload.heavy_processing_trigger is not None:
        set_heavy_processing_trigger(db, payload.heavy_processing_trigger)
    return FetchSettingsOut(
        fetch_lookback_days=get_fetch_lookback_days(db),
        default_fetch_lookback_days=settings.FETCH_LOOKBACK_DAYS,
        heavy_processing_trigger=get_heavy_processing_trigger(db),
        default_heavy_processing_trigger=DEFAULT_HEAVY_PROCESSING_TRIGGER,
    )
