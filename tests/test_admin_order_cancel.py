from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from app.modules.admin.services.orders import cancel_order


def test_cancel_order_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    admin = SimpleNamespace(id=1, role="superadmin", tenant_id=None)

    with pytest.raises(HTTPException) as exc:
        cancel_order(db, admin, 999)
    assert exc.value.status_code == 404


def test_cancel_order_already_cancelled():
    order = SimpleNamespace(
        id=123,
        order_number="LE-2026-00123",
        status="cancelled",
        tenant_id=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = order
    admin = SimpleNamespace(id=1, role="superadmin", tenant_id=None)

    result = cancel_order(db, admin, 123)
    assert result["status"] == "cancelled"
    assert "already cancelled" in result["message"]


def test_cancel_order_success():
    order = SimpleNamespace(
        id=208,
        order_number="LE-2026-00208",
        status="ready",
        tenant_id=None,
        delivery_partner_id=184,
        delivery_partner_earning=50.0,
        delivery_fee=50.0,
        cash_collected=180.0,
        notes=None,
    )
    offer1 = SimpleNamespace(id=1, status="accepted")
    offer2 = SimpleNamespace(id=2, status="offered")

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = order
    db.query.return_value.filter.return_value.all.return_value = [offer1, offer2]

    admin = SimpleNamespace(
        id=1,
        role="superadmin",
        tenant_id=None,
        full_name="Platform Admin",
        phone="9999999999",
    )

    result = cancel_order(db, admin, "LE-2026-00208", reason="Customer requested")

    assert result["status"] == "cancelled"
    assert result["order_number"] == "LE-2026-00208"
    assert order.status == "cancelled"
    assert order.cash_collected is None
    assert offer1.status == "cancelled"
    assert offer2.status == "cancelled"
    assert "Cancelled by Platform Admin: Customer requested" in order.notes
    db.commit.assert_called_once()
