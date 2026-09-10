from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.modules.admin.services.customers import (
    count_tenant_customers,
    get_all_customers,
    set_customer_status,
)
from app.modules.orders.models import Order


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.joined = []

    def join(self, *args, **kwargs):
        self.joined.append(args[0] if args else None)
        return self

    def filter(self, *args, **kwargs):
        return self

    def with_entities(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def count(self):
        return len(self.rows)

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


def _customer(**kwargs):
    values = dict(
        id=192,
        full_name="User_8870",
        phone="6394628870",
        email=None,
        is_active=True,
        created_at=datetime(2026, 9, 7, 1, 54, 38, tzinfo=timezone.utc),
        role="customer",
        tenant_id=None,
    )
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_admin_customers_include_logged_in_users_with_no_orders():
    query = _Query([_customer()])
    db = SimpleNamespace(query=lambda *a, **k: query)

    result = get_all_customers(db, tenant_id=1, page=1, q="6394628870")

    assert Order not in query.joined
    assert result["total"] == 1
    assert result["items"][0]["id"] == 192
    assert result["items"][0]["phone"] == "6394628870"


def test_admin_can_suspend_customer_who_has_not_ordered():
    customer = _customer()
    query = _Query([customer])
    db = SimpleNamespace(
        query=lambda *a, **k: query,
        commit=lambda: None,
    )

    result = set_customer_status(db, tenant_id=1, customer_id=192, is_active=False)

    assert Order not in query.joined
    assert result["is_active"] is False
    assert customer.is_active is False


def test_admin_cannot_suspend_missing_customer():
    db = SimpleNamespace(query=lambda *a, **k: _Query([]), commit=lambda: None)
    with pytest.raises(HTTPException) as exc:
        set_customer_status(db, tenant_id=1, customer_id=999, is_active=False)
    assert exc.value.status_code == 404


def test_tenant_customer_count_includes_accounts_with_no_orders():
    query = _Query([_customer(), _customer(id=193, phone="9999999999")])
    db = SimpleNamespace(query=lambda *a, **k: query)
    assert count_tenant_customers(db, tenant_id=1) == 2
    assert Order not in query.joined
