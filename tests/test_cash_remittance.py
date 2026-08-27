"""Cash remittance helpers (unit-level)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.modules.payments.cash_remittance import release_pending_remittance_orders


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
