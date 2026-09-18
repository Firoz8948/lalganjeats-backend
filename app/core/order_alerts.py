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


def notify_hotel_new_order(db: Session, order: Order) -> None:
    """SMS + loud FCM to restaurant owner when an order is ready for them.

    Call for COD at create-time, and for online prepaid only after payment
    succeeds (verify / webhook). Safe to call once per newly-paid order.
    """
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

    hotel_phone = None
    if restaurant:
        hotel_phone = restaurant.phone or (
            restaurant.owner.phone if getattr(restaurant, "owner", None) else None
        )

    customer = order.customer
    try:
        sms_mod.notify_new_order(
            order_number=order.order_number,
            customer_phone=customer.phone if customer else None,
            customer_name=_customer_first_name(db, order),
            hotel_phone=hotel_phone,
        )
    except Exception:
        logger.exception("SMS new-order notify failed for order %s", order.id)

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
            f"You received a new order #{order.order_number}. Accept now and cook it!",
            {"order_id": str(order.id), "type": "new_order"},
        )
    except Exception:
        logger.exception("FCM new-order notify failed for order %s", order.id)
