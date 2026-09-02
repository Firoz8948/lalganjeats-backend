"""Prepaid checkout visibility: an unpaid PayU attempt is not a placed order."""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_


def _method(order: Any) -> str:
    return (getattr(order, "payment_method", None) or "").strip().lower()


def _pay_status(order: Any) -> str:
    return (getattr(order, "payment_status", None) or "").strip().lower()


def unpaid_prepaid(order: Any) -> bool:
    """Online checkout started, PayU has not captured or failed yet."""
    return _method(order) == "online" and _pay_status(order) not in ("paid", "failed")


def payment_failed(order: Any) -> bool:
    return _pay_status(order) == "failed"


def customer_should_see_order(order: Any) -> bool:
    """Hide abandoned PayU attempts. Show paid orders and payment-failed rows."""
    if unpaid_prepaid(order):
        return False
    return True


def is_fulfillment_order(order: Any) -> bool:
    """Kitchen / live / dispatch only after prepaid is actually paid (COD is ok)."""
    if unpaid_prepaid(order) or payment_failed(order):
        return False
    return True


def mark_prepaid_failed(order: Any) -> bool:
    """Cancel an unpaid online order. Never rewrite a paid capture."""
    if _method(order) != "online":
        return False
    if _pay_status(order) == "paid":
        return False
    if _pay_status(order) == "failed" and (getattr(order, "status", None) or "") == "cancelled":
        return False
    order.payment_status = "failed"
    if (getattr(order, "status", None) or "") in ("pending", "awaiting_payment", ""):
        order.status = "cancelled"
    return True


def fulfillment_sql_filter(model):
    """SQLAlchemy filter: COD, or prepaid that PayU has marked paid."""
    return or_(
        model.payment_method != "online",
        model.payment_status == "paid",
    )


def customer_visible_sql_filter(model):
    """SQLAlchemy filter: hide unpaid prepaid drafts; keep paid and failed."""
    return or_(
        model.payment_method != "online",
        model.payment_status.in_(["paid", "failed"]),
    )
