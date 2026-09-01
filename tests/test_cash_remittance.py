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
