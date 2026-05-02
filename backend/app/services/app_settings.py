from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting

FETCH_LOOKBACK_DAYS_KEY = "fetch_lookback_days"
HEAVY_PROCESSING_TRIGGER_KEY = "heavy_processing_trigger"
HEAVY_PROCESSING_ON_FETCH = "on_fetch"
HEAVY_PROCESSING_ON_TO_READ = "on_to_read"
DEFAULT_HEAVY_PROCESSING_TRIGGER = HEAVY_PROCESSING_ON_TO_READ
HEAVY_PROCESSING_TRIGGERS = {
    HEAVY_PROCESSING_ON_FETCH,
    HEAVY_PROCESSING_ON_TO_READ,
}


def get_fetch_lookback_days(db: Session) -> int:
    row = db.get(AppSetting, FETCH_LOOKBACK_DAYS_KEY)
    if row is None:
        return settings.FETCH_LOOKBACK_DAYS
    try:
        value = int(row.value)
    except ValueError:
        return settings.FETCH_LOOKBACK_DAYS
    return value if value >= 1 else settings.FETCH_LOOKBACK_DAYS


def set_fetch_lookback_days(db: Session, days: int) -> int:
    row = db.get(AppSetting, FETCH_LOOKBACK_DAYS_KEY)
    if row is None:
        row = AppSetting(key=FETCH_LOOKBACK_DAYS_KEY, value=str(days))
    else:
        row.value = str(days)
        row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return days


def get_heavy_processing_trigger(db: Session) -> str:
    row = db.get(AppSetting, HEAVY_PROCESSING_TRIGGER_KEY)
    if row is None:
        return DEFAULT_HEAVY_PROCESSING_TRIGGER
    return (
        row.value
        if row.value in HEAVY_PROCESSING_TRIGGERS
        else DEFAULT_HEAVY_PROCESSING_TRIGGER
    )


def set_heavy_processing_trigger(db: Session, trigger: str) -> str:
    if trigger not in HEAVY_PROCESSING_TRIGGERS:
        raise ValueError(f"invalid heavy processing trigger: {trigger}")
    row = db.get(AppSetting, HEAVY_PROCESSING_TRIGGER_KEY)
    if row is None:
        row = AppSetting(key=HEAVY_PROCESSING_TRIGGER_KEY, value=trigger)
    else:
        row.value = trigger
        row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return trigger
