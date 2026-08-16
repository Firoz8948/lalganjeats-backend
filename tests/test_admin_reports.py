from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.admin.reports.service import (
    PUBLIC_REPORT_KEYS,
    resolve_period,
    validate_report_target,
)


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def test_daily_report_starts_at_midnight():
    start, end = resolve_period("daily", now=NOW)
    # Lalganj day boundary: midnight IST is 18:30 UTC on the previous date.
    assert start == datetime(2026, 8, 15, 18, 30, tzinfo=timezone.utc)
    assert end == NOW


def test_last_week_is_trailing_seven_days():
    start, end = resolve_period("last_week", now=NOW)
    assert end == NOW
    assert (end - start).days == 7


def test_last_month_is_trailing_thirty_days():
    start, end = resolve_period("last_month", now=NOW)
    assert end == NOW
    assert (end - start).days == 30


def test_custom_period_requires_ordered_dates():
    with pytest.raises(HTTPException) as exc:
        resolve_period(
            "custom",
            custom_start=datetime(2026, 8, 10, tzinfo=timezone.utc),
            custom_end=datetime(2026, 8, 1, tzinfo=timezone.utc),
            now=NOW,
        )
    assert exc.value.status_code == 400


def test_report_payload_never_exposes_customer_or_order_level_data():
    forbidden = {
        "customer",
        "customer_name",
        "customer_phone",
        "delivery_address",
        "order_number",
        "orders",
        "items",
    }
    assert forbidden.isdisjoint(PUBLIC_REPORT_KEYS)


def test_admin_cannot_report_target_from_another_tenant():
    admin = SimpleNamespace(role="admin", tenant_id=7)
    target = SimpleNamespace(
        id=44,
        role="delivery_partner",
        tenant_id=9,
        is_active=True,
    )
    with pytest.raises(HTTPException) as exc:
        validate_report_target(admin, target, "delivery_partner")
    assert exc.value.status_code == 404

