from datetime import date, datetime, time

from app.core.schedule_hours import (
    apply_entity_schedule,
    format_opens_at,
    is_within_hours,
    parse_hhmm,
)


def test_parse_hhmm():
    assert parse_hhmm("10:00") == time(10, 0)
    assert parse_hhmm("22:30:00") == time(22, 30)
    assert parse_hhmm(None) is None
    assert parse_hhmm("") is None


def test_format_opens_at():
    assert format_opens_at(time(10, 0)) == "Opens 10:00 AM"
    assert format_opens_at(time(22, 30)) == "Opens 10:30 PM"
    assert format_opens_at(None) is None


def test_within_hours_same_day():
    assert is_within_hours(time(10, 0), time(10, 0), time(22, 0)) is True
    assert is_within_hours(time(21, 59), time(10, 0), time(22, 0)) is True
    assert is_within_hours(time(22, 0), time(10, 0), time(22, 0)) is False
    assert is_within_hours(time(9, 59), time(10, 0), time(22, 0)) is False


def test_within_hours_overnight():
    assert is_within_hours(time(23, 0), time(18, 0), time(6, 0)) is True
    assert is_within_hours(time(5, 59), time(18, 0), time(6, 0)) is True
    assert is_within_hours(time(6, 0), time(18, 0), time(6, 0)) is False
    assert is_within_hours(time(12, 0), time(18, 0), time(6, 0)) is False


def test_auto_close_outside_hours():
    now = datetime(2026, 9, 20, 23, 0, 0)
    is_on, stamped, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        now=now,
    )
    assert is_on is False
    assert changed is True
    assert stamped == date(2026, 9, 20)


def test_auto_open_once_per_day():
    now = datetime(2026, 9, 20, 10, 5, 0)
    is_on, stamped, changed = apply_entity_schedule(
        is_on=False,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=None,
        now=now,
    )
    assert is_on is True
    assert stamped == date(2026, 9, 20)
    assert changed is True


def test_manual_close_sticks_same_day():
    now = datetime(2026, 9, 20, 15, 0, 0)
    is_on, stamped, changed = apply_entity_schedule(
        is_on=False,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        now=now,
    )
    assert is_on is False
    assert stamped == date(2026, 9, 20)
    assert changed is False


def test_always_on_skips_schedule():
    now = datetime(2026, 9, 20, 23, 0, 0)
    is_on, stamped, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=None,
        now=now,
        always_on=True,
    )
    assert is_on is True
    assert changed is False


def test_next_day_reopens_after_manual_close():
    now = datetime(2026, 9, 21, 10, 1, 0)
    is_on, stamped, changed = apply_entity_schedule(
        is_on=False,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        now=now,
    )
    assert is_on is True
    assert stamped == date(2026, 9, 21)
    assert changed is True
