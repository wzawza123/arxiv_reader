from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import FetchSettingsIn, FetchSettingsOut
from ..services.app_settings import get_fetch_lookback_days, set_fetch_lookback_days

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/fetch", response_model=FetchSettingsOut)
def get_fetch_settings(db: Session = Depends(get_db)):
    return FetchSettingsOut(
        fetch_lookback_days=get_fetch_lookback_days(db),
        default_fetch_lookback_days=settings.FETCH_LOOKBACK_DAYS,
    )


@router.patch("/fetch", response_model=FetchSettingsOut)
def update_fetch_settings(payload: FetchSettingsIn, db: Session = Depends(get_db)):
    days = set_fetch_lookback_days(db, payload.fetch_lookback_days)
    return FetchSettingsOut(
        fetch_lookback_days=days,
        default_fetch_lookback_days=settings.FETCH_LOOKBACK_DAYS,
    )
