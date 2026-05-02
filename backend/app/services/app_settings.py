from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting

FETCH_LOOKBACK_DAYS_KEY = "fetch_lookback_days"


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
