from datetime import datetime, timezone

from app.modules.admin.services import dashboard


def test_dashboard_exposes_active_offer_counter():
    assert callable(getattr(dashboard, "count_active_promos", None))


def test_active_offer_filter_uses_current_time():
    filters = dashboard.active_promo_filters(
        tenant_id=7,
        now=datetime(2026, 8, 16, tzinfo=timezone.utc),
    )
    assert len(filters) == 4
