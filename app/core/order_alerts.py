"""Partner-facing new-order alerts (SMS + loud FCM)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core import sms as sms_mod
from app.core.fcm import send_push_notification
from app.modules.orders.models import Order

logger = logging.getLogger(__name__)


def _customer_first_name(db: Session, order: Order) -> str:
    customer = order.customer
    if not customer:
        return "Customer"
    name = (customer.full_name or "").strip() or "Customer"
    if name.lower().startswith("user_"):
        from app.modules.users.models import CustomerProfile

        prof = (
            db.query(CustomerProfile)
            .filter(CustomerProfile.user_id == customer.id)
            .first()
        )
        if prof and (prof.full_name or "").strip():
            name = prof.full_name.strip()
    return name.split()[0]


def _order_restaurant(db: Session, order: Order):
    from app.modules.restaurants.models import Restaurant

    # Re-load so owner.fcm_token is available after commit / detached instances.
    restaurant = None
    if order.restaurant_id:
        restaurant = (
            db.query(Restaurant)
            .filter(Restaurant.id == order.restaurant_id)
            .first()
        )
    if restaurant is None:
        restaurant = order.restaurant
    return restaurant


def _hotel_phone(restaurant) -> str | None:
    if not restaurant:
        return None
    return restaurant.phone or (
        restaurant.owner.phone if getattr(restaurant, "owner", None) else None
    )


def _push_owner(restaurant, order: Order, body: str) -> None:
    owner = getattr(restaurant, "owner", None) if restaurant else None
    token = getattr(owner, "fcm_token", None) if owner else None
    if not token:
        logger.warning(
            "[FCM] No restaurant owner token for order %s (restaurant_id=%s)",
            order.id,
            getattr(order, "restaurant_id", None),
        )
        return

    try:
        send_push_notification(
            token,
            "New Order Received!",
            body,
            {"order_id": str(order.id), "type": "new_order"},
        )
    except Exception:
        logger.exception("FCM new-order notify failed for order %s", order.id)


def notify_hotel_new_order(db: Session, order: Order) -> None:
    """SMS + loud FCM to restaurant owner when an order is ready for them.

    Call for COD at create-time, and for online prepaid only after payment
    succeeds (verify / webhook). Safe to call once per newly-paid order.
    """
    if getattr(order, "is_multi_store", False):
        notify_multi_store_order(db, order)
        return

    restaurant = _order_restaurant(db, order)
    customer = order.customer
    try:
        sms_mod.notify_new_order(
            order_number=order.order_number,
            customer_phone=customer.phone if customer else None,
            customer_name=_customer_first_name(db, order),
            hotel_phone=_hotel_phone(restaurant),
        )
    except Exception:
        logger.exception("SMS new-order notify failed for order %s", order.id)

    _push_owner(
        restaurant,
        order,
        f"You received a new order #{order.order_number}. Accept now and cook it!",
    )


def notify_multi_store_order(db: Session, parent: Order) -> None:
    """Customer + admins hear about the parent once; each store gets its sub-order."""
    customer = parent.customer
    try:
        sms_mod.notify_new_order(
            order_number=parent.order_number,
            customer_phone=customer.phone if customer else None,
            customer_name=_customer_first_name(db, parent),
            hotel_phone=None,
        )
    except Exception:
        logger.exception("SMS new-order notify failed for order %s", parent.id)

    for sub in parent.sub_orders or []:
        restaurant = _order_restaurant(db, sub)
        phone = _hotel_phone(restaurant)
        if phone:
            try:
                sms_mod.send_order_alert(phone, sub.order_number)
            except Exception:
                logger.exception("Store SMS alert failed for order %s", sub.id)
        _push_owner(
            restaurant,
            sub,
            f"You received a new order #{sub.order_number}. Accept now and pack it!",
        )
