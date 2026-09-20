from datetime import date, datetime, time

from app.core.schedule_hours import (
    apply_entity_schedule,
    format_opens_at,
    is_within_hours,
    parse_hhmm,
    schedule_period_date,
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


def test_schedule_period_overnight_morning():
    now = datetime(2026, 9, 21, 5, 0, 0)
    assert schedule_period_date(now, time(18, 0), time(6, 0)) == date(2026, 9, 20)


def test_auto_close_at_closing_time():
    now = datetime(2026, 9, 20, 22, 0, 0)
    is_on, on_date, off_date, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=None,
        now=now,
    )
    assert is_on is False
    assert changed is True
    assert on_date == date(2026, 9, 20)
    assert off_date == date(2026, 9, 20)


def test_auto_open_once_per_day():
    now = datetime(2026, 9, 20, 10, 5, 0)
    is_on, on_date, off_date, changed = apply_entity_schedule(
        is_on=False,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=None,
        schedule_off_date=None,
        now=now,
    )
    assert is_on is True
    assert on_date == date(2026, 9, 20)
    assert changed is True


def test_already_open_at_opening_time_stays_open():
    now = datetime(2026, 9, 20, 10, 0, 0)
    is_on, on_date, _, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=None,
        now=now,
    )
    assert is_on is True
    assert on_date == date(2026, 9, 20)
    assert changed is True  # stamp only


def test_manual_close_sticks_same_day():
    now = datetime(2026, 9, 20, 15, 0, 0)
    is_on, on_date, off_date, changed = apply_entity_schedule(
        is_on=False,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=None,
        now=now,
    )
    assert is_on is False
    assert on_date == date(2026, 9, 20)
    assert changed is False


def test_manual_open_outside_hours_sticks():
    """After scheduled close, admin/hotel 'Open now' must not be undone."""
    now = datetime(2026, 9, 20, 23, 0, 0)
    is_on, on_date, off_date, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=date(2026, 9, 20),
        now=now,
    )
    assert is_on is True
    assert changed is False
    assert off_date == date(2026, 9, 20)


def test_note_manual_open_outside_prevents_force_close():
    from app.core.schedule_hours import note_manual_shop_state

    now = datetime(2026, 9, 20, 23, 0, 0)
    on_date, off_date = note_manual_shop_state(
        is_open=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=None,
        now=now,
    )
    assert on_date == date(2026, 9, 20)
    assert off_date == date(2026, 9, 20)
    is_on, _, _, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=on_date,
        schedule_off_date=off_date,
        now=now,
    )
    assert is_on is True
    assert changed is False


def test_manual_open_before_opening_sticks():
    now = datetime(2026, 9, 20, 9, 0, 0)
    is_on, _, _, changed = apply_entity_schedule(
        is_on=True,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=None,
        schedule_off_date=None,
        now=now,
    )
    assert is_on is True
    assert changed is False


def test_always_on_skips_schedule():
    now = datetime(2026, 9, 20, 23, 0, 0)
    is_on, _, _, changed = apply_entity_schedule(
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
    is_on, on_date, _, changed = apply_entity_schedule(
        is_on=False,
        opening=time(10, 0),
        closing=time(22, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=date(2026, 9, 20),
        now=now,
    )
    assert is_on is True
    assert on_date == date(2026, 9, 21)
    assert changed is True


def test_overnight_manual_close_sticks_past_midnight():
    now = datetime(2026, 9, 21, 2, 0, 0)
    is_on, on_date, _, changed = apply_entity_schedule(
        is_on=False,
        opening=time(18, 0),
        closing=time(6, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=None,
        now=now,
    )
    assert is_on is False
    assert on_date == date(2026, 9, 20)
    assert changed is False


def test_overnight_closes_after_closing_time():
    now = datetime(2026, 9, 21, 6, 0, 0)
    is_on, on_date, off_date, changed = apply_entity_schedule(
        is_on=True,
        opening=time(18, 0),
        closing=time(6, 0),
        schedule_on_date=date(2026, 9, 20),
        schedule_off_date=None,
        now=now,
    )
    assert is_on is False
    assert changed is True
    assert off_date == date(2026, 9, 20)
    assert on_date == date(2026, 9, 20)
