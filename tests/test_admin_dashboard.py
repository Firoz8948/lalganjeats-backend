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


def test_dashboard_customer_total_counts_registered_accounts():
    import inspect

    source = inspect.getsource(dashboard.get_dashboard)
    assert "count_tenant_customers" in source
    assert "Order.customer_id" not in source


def test_order_number_sequence_includes_failed_and_cancelled():
    assert dashboard.sequence_from_order_number("LE-2026-00146") == 146
    assert dashboard.sequence_from_order_number("LE-2026-00001") == 1
    assert dashboard.sequence_from_order_number(None) == 0


def test_dashboard_total_orders_uses_latest_sequence():
    import inspect
    from types import SimpleNamespace

    source = inspect.getsource(dashboard.get_dashboard)
    assert "latest_order_sequence" in source
    assert "orders_q.count()" not in source

    class _Query:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            return SimpleNamespace(
                order_number="LE-2026-00146",
                status="cancelled",
                payment_status="failed",
            )

    db = SimpleNamespace(query=lambda *a, **k: _Query())
    assert dashboard.latest_order_sequence(db, tenant_id=1) == 146
