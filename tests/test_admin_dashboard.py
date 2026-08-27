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


def test_dashboard_revenue_counts_delivered_orders_for_tenant():
    filters = dashboard.delivered_revenue_filters(tenant_id=7)

    assert len(filters) == 2
    assert filters[0].left.key == "status"
    assert filters[0].right.value == "delivered"
    assert filters[1].left.key == "tenant_id"
    assert filters[1].right.value == 7


def test_live_orders_exclude_delivered_and_cancelled():
    assert "delivered" not in dashboard.LIVE_ORDER_STATUSES
    assert "cancelled" not in dashboard.LIVE_ORDER_STATUSES
    assert "pending" in dashboard.LIVE_ORDER_STATUSES
    assert "accepted" in dashboard.LIVE_ORDER_STATUSES
    assert "picked_up" in dashboard.LIVE_ORDER_STATUSES
    assert "on_the_way" not in dashboard.LIVE_ORDER_STATUSES
