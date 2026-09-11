"""Cash remittance helpers (unit-level)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.payments.cash_remittance import (
    encode_order_ids,
    parse_order_ids,
    release_pending_remittance_orders,
)


def test_parse_and_encode_order_ids():
    assert parse_order_ids(None) == []
    assert parse_order_ids("1,2,3") == [1, 2, 3]
    orders = [SimpleNamespace(id=10), SimpleNamespace(id=11)]
    assert encode_order_ids(orders) == "10,11"


def test_release_pending_unlinks_orders_and_marks_failed():
    order = SimpleNamespace(cash_remittance_id=3)
    remit = SimpleNamespace(id=3, status="pending")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [order]

    release_pending_remittance_orders(db, remit)

    assert order.cash_remittance_id is None
    assert remit.status == "failed"
    db.commit.assert_called_once()


def test_release_skips_already_paid():
    remit = SimpleNamespace(id=3, status="paid")
    db = MagicMock()
    release_pending_remittance_orders(db, remit)
    db.query.assert_not_called()
    db.commit.assert_not_called()


def test_attach_skips_orders_already_on_paid_remit():
    from app.modules.payments.cash_remittance import _attach_orders_to_paid_remittance

    already = SimpleNamespace(id=1, cash_remittance_id=9)
    free = SimpleNamespace(id=2, cash_remittance_id=None)
    remit = SimpleNamespace(id=5, order_ids="1,2")
    paid_other = SimpleNamespace(id=9, status="paid")

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [already, free]
    db.query.return_value.filter.return_value.first.return_value = paid_other

    _attach_orders_to_paid_remittance(db, remit)

    assert already.cash_remittance_id == 9
    assert free.cash_remittance_id == 5


def test_clear_delivery_partner_cash(monkeypatch):
    import app.main  # noqa: F401 - registers all SQLAlchemy mappers
    from app.modules.admin.services.settlements import clear_delivery_partner_cash

    admin = SimpleNamespace(id=1, role="superadmin", tenant_id=None)
    partner = SimpleNamespace(id=42, role="delivery_partner", tenant_id=None, full_name="Rider One", phone="9876543210")
    order1 = SimpleNamespace(id=101, cash_collected=1500.0, cash_remittance_id=None, tenant_id=None)
    order2 = SimpleNamespace(id=102, cash_collected=2834.0, cash_remittance_id=None, tenant_id=None)

    db = MagicMock()
    def fake_add(obj):
        obj.id = 88
    db.add.side_effect = fake_add
    # No stale pending remittances
    db.query.return_value.filter.return_value.all.return_value = []

    monkeypatch.setattr(
        "app.modules.admin.services.settlements._owned_delivery_partner",
        lambda _db, _curr, _pid: partner,
    )
    monkeypatch.setattr(
        "app.modules.payments.cash_remittance.unremitted_cash_orders",
        lambda _db, _pid: [order1, order2],
    )

    result = clear_delivery_partner_cash(db, admin, partner.id)

    assert result["cleared_amount"] == 4334.0
    assert result["cleared_orders"] == 2
    assert "Successfully cleared cash of ₹4334.00" in result["message"]
    assert order1.cash_remittance_id is not None
    assert order2.cash_remittance_id is not None
    db.commit.assert_called_once()

