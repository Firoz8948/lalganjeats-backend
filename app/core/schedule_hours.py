"""Opening / closing schedule helpers (Asia/Kolkata)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
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


def schedule_period_date(now: datetime, opening: time, closing: time) -> date:
    """
    Calendar date of the opening that owns the current (or just-ended) window.
    Overnight morning hours still belong to yesterday's opening.
    """
    day = now.date()
    now_t = now.time().replace(tzinfo=None, microsecond=0)
    opening = opening.replace(tzinfo=None, microsecond=0)
    closing = closing.replace(tzinfo=None, microsecond=0)
    if opening < closing or opening == closing:
        return day
    if now_t < closing:
        return day - timedelta(days=1)
    return day


def apply_entity_schedule(
    *,
    is_on: bool,
    opening: time | None,
    closing: time | None,
    schedule_on_date: date | None,
    schedule_off_date: date | None = None,
    now: datetime | None = None,
    always_on: bool = False,
) -> tuple[bool, date | None, date | None, bool]:
    """
    Returns (new_is_on, new_schedule_on_date, new_schedule_off_date, changed).

    Manual open/close always sticks between scheduled edges:
    - At opening (first tick inside a period) → turn ON if not already on
    - At closing (first tick outside after that period opened) → turn OFF
    - Outside hours after a scheduled close → leave manual reopen alone
    - Inside hours after open stamp → leave manual mid-day close alone
    """
    if always_on or opening is None or closing is None:
        return is_on, schedule_on_date, schedule_off_date, False

    current = now or now_ist()
    period = schedule_period_date(current, opening, closing)
    within = is_within_hours(current.time(), opening, closing)

    if within:
        if schedule_on_date != period:
            changed = (not is_on) or (schedule_on_date != period)
            return True, period, schedule_off_date, changed
        # Already auto-opened this period — respect manual mid-day close/open.
        return is_on, schedule_on_date, schedule_off_date, False

    # Outside hours: scheduled close once per opened period, then leave alone.
    if (
        is_on
        and schedule_on_date is not None
        and schedule_off_date != schedule_on_date
    ):
        return False, schedule_on_date, schedule_on_date, True

    return is_on, schedule_on_date, schedule_off_date, False


def note_manual_shop_state(
    *,
    is_open: bool,
    opening: time | None,
    closing: time | None,
    schedule_on_date: date | None,
    schedule_off_date: date | None,
    now: datetime | None = None,
) -> tuple[date | None, date | None]:
    """
    Adjust schedule stamps after a manual open/close so the scheduler
    does not immediately undo the change.
    """
    if opening is None or closing is None:
        return schedule_on_date, schedule_off_date

    current = now or now_ist()
    period = schedule_period_date(current, opening, closing)
    within = is_within_hours(current.time(), opening, closing)

    if is_open and not within:
        # Manual open outside hours: mark this period as already closed
        # so the next tick won't force-close again.
        on_date = schedule_on_date or period
        return on_date, on_date

    if (not is_open) and within and schedule_on_date == period:
        # Manual mid-day close: keep open stamp so we don't auto-reopen today.
        return schedule_on_date, schedule_off_date

    return schedule_on_date, schedule_off_date
