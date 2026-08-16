from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.orders.service import validate_payment_method


def _settings(**overrides):
    values = {
        "allow_prepaid_orders": True,
        "allow_cod_orders": True,
        "cod_max_order_amount": 500,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_cod_is_allowed_below_threshold():
    validate_payment_method("cash", 499.99, _settings())


def test_cod_is_rejected_at_threshold():
    with pytest.raises(HTTPException) as exc:
        validate_payment_method("cash", 500, _settings())
    assert exc.value.status_code == 400
    assert "prepaid" in exc.value.detail.lower()


def test_prepaid_can_be_disabled_by_admin():
    with pytest.raises(HTTPException):
        validate_payment_method(
            "online",
            100,
            _settings(allow_prepaid_orders=False),
        )
