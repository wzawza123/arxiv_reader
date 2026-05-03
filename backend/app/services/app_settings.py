from __future__ import annotations

from datetime import datetime
import re

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting

FETCH_LOOKBACK_DAYS_KEY = "fetch_lookback_days"
AUTO_FETCH_ENABLED_KEY = "auto_fetch_enabled"
FETCH_TIME_KEY = "fetch_time"
HEAVY_PROCESSING_TRIGGER_KEY = "heavy_processing_trigger"
DEFAULT_AUTO_FETCH_ENABLED = True
HEAVY_PROCESSING_ON_FETCH = "on_fetch"
HEAVY_PROCESSING_ON_TO_READ = "on_to_read"
DEFAULT_HEAVY_PROCESSING_TRIGGER = HEAVY_PROCESSING_ON_TO_READ
HEAVY_PROCESSING_TRIGGERS = {
    HEAVY_PROCESSING_ON_FETCH,
    HEAVY_PROCESSING_ON_TO_READ,
}
FETCH_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def default_fetch_time() -> str:
    value = f"{settings.FETCH_CRON_HOUR:02d}:{settings.FETCH_CRON_MINUTE:02d}"
    return value if is_valid_fetch_time(value) else "09:00"


def is_valid_fetch_time(value: str) -> bool:
    return bool(FETCH_TIME_RE.match(value))


def parse_fetch_time(value: str) -> tuple[int, int]:
    if not is_valid_fetch_time(value):
        raise ValueError(f"invalid fetch time: {value}")
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def _upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.add(row)


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
    _upsert_setting(db, FETCH_LOOKBACK_DAYS_KEY, str(days))
    db.commit()
    return days


def get_auto_fetch_enabled(db: Session) -> bool:
    row = db.get(AppSetting, AUTO_FETCH_ENABLED_KEY)
    if row is None:
        return DEFAULT_AUTO_FETCH_ENABLED
    value = row.value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return DEFAULT_AUTO_FETCH_ENABLED


def set_auto_fetch_enabled(db: Session, enabled: bool) -> bool:
    _upsert_setting(db, AUTO_FETCH_ENABLED_KEY, "true" if enabled else "false")
    db.commit()
    return enabled


def get_fetch_time(db: Session) -> str:
    row = db.get(AppSetting, FETCH_TIME_KEY)
    if row is None:
        return default_fetch_time()
    value = row.value.strip()
    return value if is_valid_fetch_time(value) else default_fetch_time()


def set_fetch_time(db: Session, fetch_time: str) -> str:
    if not is_valid_fetch_time(fetch_time):
        raise ValueError(f"invalid fetch time: {fetch_time}")
    _upsert_setting(db, FETCH_TIME_KEY, fetch_time)
    db.commit()
    return fetch_time


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
    _upsert_setting(db, HEAVY_PROCESSING_TRIGGER_KEY, trigger)
    db.commit()
    return trigger
