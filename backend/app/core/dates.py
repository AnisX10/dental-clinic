"""Clinic-wide time helpers. All "today"/"now" logic uses Africa/Algiers."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("Africa/Algiers")


def now_tz() -> datetime:
    return datetime.now(CLINIC_TZ)


def today() -> date:
    return now_tz().date()
