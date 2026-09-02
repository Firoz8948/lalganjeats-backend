from types import SimpleNamespace

from app.modules.orders.payment_state import (
    customer_should_see_order,
    is_fulfillment_order,
    mark_prepaid_failed,
    unpaid_prepaid,
)


def _order(**kwargs):
    values = dict(
        payment_method="online",
        payment_status="pending",
        status="pending",
    )
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_unpaid_prepaid_is_not_a_placed_order():
    unpaid = _order()
    assert unpaid_prepaid(unpaid) is True
    assert customer_should_see_order(unpaid) is False
    assert is_fulfillment_order(unpaid) is False


def test_paid_prepaid_is_visible_and_live():
    paid = _order(payment_status="paid")
    assert unpaid_prepaid(paid) is False
    assert customer_should_see_order(paid) is True
    assert is_fulfillment_order(paid) is True


def test_failed_prepaid_shows_as_payment_failed_not_placed():
    failed = _order(payment_status="failed", status="cancelled")
    assert unpaid_prepaid(failed) is False
    assert customer_should_see_order(failed) is True
    assert is_fulfillment_order(failed) is False


def test_cod_pending_is_a_real_order():
    cod = _order(payment_method="cash", payment_status="pending")
    assert unpaid_prepaid(cod) is False
    assert customer_should_see_order(cod) is True
    assert is_fulfillment_order(cod) is True


def test_mark_prepaid_failed_cancels_unpaid_online_order():
    order = _order()
    assert mark_prepaid_failed(order) is True
    assert order.payment_status == "failed"
    assert order.status == "cancelled"


def test_mark_prepaid_failed_does_not_touch_paid_order():
    order = _order(payment_status="paid", status="pending")
    assert mark_prepaid_failed(order) is False
    assert order.payment_status == "paid"
    assert order.status == "pending"
