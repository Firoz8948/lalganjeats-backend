"""Opening / closing schedule helpers (Asia/Kolkata)."""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def parse_hhmm(value) -> time | None:
    """Accept time | 'HH:MM' | 'HH:MM:SS' | None."""
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value.replace(tzinfo=None, microsecond=0)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time '{value}'. Use HH:MM (24h).")


def format_hhmm(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def format_opens_at(opening: time | None) -> str | None:
    """Customer-facing label, e.g. 'Opens 10:00 AM'."""
    if opening is None:
        return None
    label = opening.strftime("%I:%M %p")
    if label.startswith("0"):
        label = label[1:]
    return f"Opens {label}"


def is_within_hours(now_t: time, opening: time, closing: time) -> bool:
    """
    Half-open window [opening, closing).
    Supports overnight ranges (e.g. 22:00 → 06:00).
    If opening == closing, treat as always within hours.
    """
    now_t = now_t.replace(tzinfo=None, microsecond=0)
    opening = opening.replace(tzinfo=None, microsecond=0)
    closing = closing.replace(tzinfo=None, microsecond=0)
    if opening == closing:
        return True
    if opening < closing:
        return opening <= now_t < closing
    return now_t >= opening or now_t < closing


def apply_entity_schedule(
    *,
    is_on: bool,
    opening: time | None,
    closing: time | None,
    schedule_on_date: date | None,
    now: datetime | None = None,
    always_on: bool = False,
) -> tuple[bool, date | None, bool]:
    """
    Returns (new_is_on, new_schedule_on_date, changed).

    - always_on / missing hours → unchanged
    - outside hours → force off
    - inside hours, first time today → force on + stamp date
    - inside hours after stamp → leave alone (manual mid-day off sticks)
    """
    if always_on or opening is None or closing is None:
        return is_on, schedule_on_date, False

    current = now or now_ist()
    today = current.date()
    within = is_within_hours(current.time(), opening, closing)

    if not within:
        if is_on:
            return False, schedule_on_date, True
        return is_on, schedule_on_date, False

    if schedule_on_date != today:
        changed = (not is_on) or (schedule_on_date != today)
        return True, today, changed

    return is_on, schedule_on_date, False
