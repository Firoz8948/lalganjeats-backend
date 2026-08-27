"""Revenue ledger composition rules (no DB)."""
from types import SimpleNamespace

from app.modules.payments.revenue import compose_revenue_rows


def _order(**kwargs):
    defaults = dict(
        id=1,
        order_number="LE-1",
        total_amount=500,
        cash_collected=None,
        online_collected=None,
        payment_status="paid",
        status="delivered",
        created_at=None,
        customer=SimpleNamespace(full_name="Riya"),
        delivery_partner=SimpleNamespace(full_name="Amit DP"),
        restaurant=SimpleNamespace(name="Hotel X"),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_prepaid_shows_customer_name_and_amount():
    rows = compose_revenue_rows(
        orders=[_order(total_amount=350, cash_collected=0, online_collected=0)],
        remittances=[],
    )
    assert len(rows) == 1
    assert rows[0]["source_type"] == "customer"
    assert rows[0]["payer_name"] == "Riya"
    assert rows[0]["amount"] == 350
    assert rows[0]["method"] == "prepaid_online"


def test_doorstep_online_via_delivery_partner():
    rows = compose_revenue_rows(
        orders=[
            _order(
                cash_collected=0,
                online_collected=400,
                total_amount=400,
            )
        ],
        remittances=[],
    )
    assert len(rows) == 1
    assert rows[0]["source_type"] == "customer"
    assert rows[0]["via"] == "Amit DP"
    assert "Amit DP" in rows[0]["label"]
    assert rows[0]["amount"] == 400


def test_unremitted_cash_is_not_revenue():
    rows = compose_revenue_rows(
        orders=[
            _order(
                cash_collected=500,
                online_collected=0,
                total_amount=500,
            )
        ],
        remittances=[],
    )
    assert rows == []


def test_cash_remittance_is_delivery_partner_revenue():
    remit = SimpleNamespace(
        id=9,
        amount=500,
        status="paid",
        paid_at=None,
        created_at=None,
        delivery_partner=SimpleNamespace(full_name="Amit DP"),
        orders=[SimpleNamespace(order_number="LE-99")],
    )
    rows = compose_revenue_rows(orders=[], remittances=[remit])
    assert len(rows) == 1
    assert rows[0]["source_type"] == "delivery_partner"
    assert rows[0]["payer_name"] == "Amit DP"
    assert rows[0]["label"] == "Cash payment cleared"
    assert rows[0]["amount"] == 500


def test_split_doorstep_only_counts_online_until_cash_cleared():
    rows = compose_revenue_rows(
        orders=[
            _order(
                cash_collected=200,
                online_collected=300,
                total_amount=500,
            )
        ],
        remittances=[],
    )
    assert len(rows) == 1
    assert rows[0]["amount"] == 300
    assert rows[0]["method"] == "doorstep_online"
