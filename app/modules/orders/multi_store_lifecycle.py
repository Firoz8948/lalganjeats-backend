# backend/app/modules/orders/multi_store_lifecycle.py
"""Keeps a multi-store parent order and its per-store sub-orders in step.

- Stores move their own sub-order (accept → ready, or cancel).
- The parent's status is derived: riders are offered the parent as soon as
  one store accepts, and can pick up once every remaining store is ready.
- A store cancelling only drops its share: totals are recomputed and, for
  prepaid orders, the difference is refunded. Fees stay with the parent.
- Rider pickup / delivery on the parent is copied down to the live stores.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.orders.models import DeliveryOffer, Order

logger = logging.getLogger(__name__)

RIDER_OWNED_STATUSES = ("picked_up", "out_for_delivery", "delivered", "cancelled")


def live_sub_orders(parent: Order) -> list[Order]:
    return [s for s in (parent.sub_orders or []) if s.status != "cancelled"]


def shown_sub_orders(order) -> list[Order]:
    """Live stores; all of them once the whole order is cancelled."""
    return live_sub_orders(order) or list(order.sub_orders or [])


def pickup_restaurants(order) -> list:
    if getattr(order, "is_multi_store", False):
        return [s.restaurant for s in shown_sub_orders(order) if s.restaurant is not None]
    restaurant = getattr(order, "restaurant", None)
    return [restaurant] if restaurant is not None else []


def restaurant_label(order) -> str | None:
    names = [r.name for r in pickup_restaurants(order)]
    return " + ".join(names) if names else None


def order_lines(order) -> list:
    """Item rows to show for an order; a parent shows its stores' items."""
    if getattr(order, "is_multi_store", False):
        return [item for sub in shown_sub_orders(order) for item in (sub.items or [])]
    return list(getattr(order, "items", None) or [])


def derived_parent_status(parent: Order) -> str:
    if parent.status in RIDER_OWNED_STATUSES:
        return parent.status
    live = live_sub_orders(parent)
    if not live:
        return "cancelled"
    if all(s.status == "ready" for s in live):
        return "ready"
    if any(s.status in ("accepted", "ready") for s in live):
        return "accepted"
    return "pending"


def _snapshot_discount(parent: Order, subtotal: float) -> Decimal:
    """Re-apply the promo saved on the parent to a smaller cart."""
    if not parent.promo_code_id and not parent.promo_code:
        return Decimal(str(parent.discount or 0))
    sub = Decimal(str(subtotal))
    if (parent.promo_discount_type or "") == "flat":
        flat = Decimal(str(parent.promo_flat_off or 0))
        return min(flat, sub).quantize(Decimal("0.01")) if flat > 0 else Decimal("0")
    if parent.promo_percent_off:
        return (sub * Decimal(str(parent.promo_percent_off)) / Decimal("100")).quantize(
            Decimal("0.01")
        )
    return min(Decimal(str(parent.discount or 0)), sub)


def recompute_parent_totals(parent: Order) -> None:
    from app.modules.payments.breakdown import breakdown_from_order

    live = live_sub_orders(parent)
    display = round(sum(float(s.display_total or 0) for s in live), 2)
    actual = round(sum(float(s.actual_total or 0) for s in live), 2)
    packing = round(sum(float(s.packing_charge or 0) for s in live), 2)

    parent.subtotal = Decimal(str(display))
    parent.display_total = Decimal(str(display))
    parent.actual_total = Decimal(str(actual))
    parent.packing_charge = Decimal(str(packing))
    parent.discount = _snapshot_discount(parent, display)

    bd = breakdown_from_order(parent)
    parent.total_amount = Decimal(str(bd.customer.customer_total))
    parent.admin_earning = Decimal(str(bd.admin.admin_profit))


def _append_note(order: Order, text: str) -> None:
    order.notes = f"{order.notes} | {text}" if order.notes else text


def _drop_unsettled_earnings(db: Session, order_id: int) -> None:
    from app.modules.payments.models import DeliveryEarning, RestaurantEarning

    for model in (RestaurantEarning, DeliveryEarning):
        db.query(model).filter(
            model.order_id == order_id,
            model.transfer_status.in_(["unsettled", "pending"]),
        ).delete(synchronize_session=False)


def _close_offers(db: Session, order_id: int) -> None:
    db.query(DeliveryOffer).filter(
        DeliveryOffer.order_id == order_id,
        DeliveryOffer.status.in_(["offered", "accepted"]),
    ).update({"status": "cancelled"}, synchronize_session=False)


def _refund(db: Session, parent: Order, amount: float, label: str) -> None:
    amount = round(amount, 2)
    if amount <= 0 or not parent.razorpay_payment_id:
        return
    from app.core.razorpay_service import refund_payment

    try:
        refund = refund_payment(
            parent.razorpay_payment_id,
            amount,
            notes={"order_id": str(parent.id), "reason": label[:200]},
        )
        parent.refunded_amount = Decimal(str(round(float(parent.refunded_amount or 0) + amount, 2)))
        _append_note(parent, f"Refunded ₹{amount:g} ({label}, {refund.get('id', 'refund')})")
    except Exception:
        logger.exception("Refund of ₹%s failed for order %s", amount, parent.id)
        _append_note(parent, f"REFUND PENDING ₹{amount:g} ({label}) - refund manually")
    db.commit()


def cancel_store_share(db: Session, sub: Order, reason: str) -> None:
    """Drop one store from a multi-store order and settle the money difference."""
    parent = sub.parent_order
    if parent is None or sub.status == "cancelled":
        return
    if parent.status in ("picked_up", "out_for_delivery", "delivered"):
        from fastapi import HTTPException

        raise HTTPException(400, "The rider has already picked up this order")

    sub.status = "cancelled"
    _append_note(sub, reason)
    _drop_unsettled_earnings(db, sub.id)

    prepaid = parent.payment_method == "online" and parent.payment_status == "paid"
    old_total = float(parent.total_amount or 0)

    if not live_sub_orders(parent):
        parent.status = "cancelled"
        _close_offers(db, parent.id)
        _drop_unsettled_earnings(db, parent.id)
        _append_note(parent, f"All stores cancelled ({reason})")
        refund_amount = old_total
    else:
        recompute_parent_totals(parent)
        _append_note(parent, f"{sub.order_number} cancelled ({reason})")
        refund_amount = old_total - float(parent.total_amount or 0)
    db.commit()

    if prepaid:
        _refund(db, parent, refund_amount, f"{sub.order_number} cancelled")


def on_sub_order_status_changed(db: Session, sub: Order) -> None:
    """Call after a store accepted / readied / cancelled its sub-order."""
    parent = sub.parent_order
    if parent is None:
        return

    prev_parent = parent.status
    parent.status = derived_parent_status(parent)
    db.commit()

    if prev_parent == "pending" and parent.status in ("accepted", "ready"):
        from app.modules.delivery.dispatch import start_dispatch

        start_dispatch(parent.id)

    from app.modules.tracking.service import broadcast_order_tracking

    broadcast_order_tracking(db, parent.id)


def propagate_rider_status(parent: Order) -> None:
    """Rider moved the parent (picked up / delivered): mirror it on each store."""
    if not getattr(parent, "is_multi_store", False):
        return
    for sub in live_sub_orders(parent):
        sub.status = parent.status
        if parent.status == "delivered":
            sub.payment_status = parent.payment_status
            sub.payment_method = parent.payment_method
