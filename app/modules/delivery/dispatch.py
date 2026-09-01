"""
Nearest-first delivery partner cascade (tenant-scoped).

Rules:
- Only online partners with GPS, same tenant as the order/restaurant
- Rank by distance to restaurant
- Offer to rank 1 first; on reject → immediate next; on silence → wait N seconds then expand
- Accept locks the order exclusively
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.maps import distance_and_drive_minutes, maps_embed_url
from app.core import sms
from app.modules.orders.models import Order, DeliveryProfile, DeliveryOffer
from app.modules.users.models import User
from app.modules.delivery import webhook as dp_webhook

logger = logging.getLogger(__name__)

WAIT_SECONDS = lambda: int(getattr(settings, "DELIVERY_OFFER_WAIT_SECONDS", 10) or 10)


def _restaurant_coords(order: Order):
    r = order.restaurant
    if not r or r.latitude is None or r.longitude is None:
        return None, None
    return float(r.latitude), float(r.longitude)


def ranked_partners(db: Session, order: Order) -> list[tuple[User, DeliveryProfile, float]]:
    """Return [(user, profile, distance_km), ...] nearest first, same tenant only."""
    tenant_id = order.tenant_id or (order.restaurant.tenant_id if order.restaurant else None)
    r_lat, r_lng = _restaurant_coords(order)
    if r_lat is None:
        return []

    q = (
        db.query(User, DeliveryProfile)
        .join(DeliveryProfile, DeliveryProfile.user_id == User.id)
        .filter(
            User.role == "delivery_partner",
            User.is_active == True,
            DeliveryProfile.is_online == True,
            DeliveryProfile.current_latitude.isnot(None),
            DeliveryProfile.current_longitude.isnot(None),
        )
    )
    if tenant_id is not None:
        q = q.filter(User.tenant_id == tenant_id)

    rows = q.all()
    ranked = []
    for user, profile in rows:
        km, _ = distance_and_drive_minutes(
            float(profile.current_latitude),
            float(profile.current_longitude),
            r_lat,
            r_lng,
        )
        ranked.append((user, profile, km))
    ranked.sort(key=lambda x: x[2])
    return ranked


def start_dispatch(order_id: int) -> None:
    """Broadcast delivery offer immediately to all active online delivery partners."""
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return
        if order.delivery_partner_id:
            return
        if order.status not in ("accepted", "ready"):
            return

        tenant_id = order.tenant_id or (order.restaurant.tenant_id if order.restaurant else None)
        r_lat, r_lng = _restaurant_coords(order)

        q = (
            db.query(User, DeliveryProfile)
            .join(DeliveryProfile, DeliveryProfile.user_id == User.id)
            .filter(
                User.role == "delivery_partner",
                User.is_active == True,
                DeliveryProfile.is_online == True,
            )
        )
        if tenant_id is not None:
            q = q.filter(User.tenant_id == tenant_id)

        partners = q.all()
        if not partners:
            logger.info("No online DPs available to broadcast order %s", order_id)
            return

        for user, profile in partners:
            km = 0.0
            if r_lat is not None and profile.current_latitude is not None and profile.current_longitude is not None:
                try:
                    km, _ = distance_and_drive_minutes(
                        float(profile.current_latitude),
                        float(profile.current_longitude),
                        r_lat,
                        r_lng,
                    )
                except Exception:
                    km = 0.0

            existing = (
                db.query(DeliveryOffer)
                .filter(
                    DeliveryOffer.order_id == order_id,
                    DeliveryOffer.delivery_partner_id == user.id,
                )
                .first()
            )
            if not existing:
                offer = DeliveryOffer(
                    order_id=order_id,
                    delivery_partner_id=user.id,
                    rank=1,
                    distance_km=km,
                    status="offered",
                    expires_at=None,
                )
                db.add(offer)
                logger.info("Broadcast offered order %s to DP %s (km=%s)", order_id, user.id, km)
            elif existing.status in ("expired", "superseded"):
                existing.status = "offered"
                existing.expires_at = None

        db.commit()

        # Send FCM multicast push to all online delivery partners
        fcm_tokens = [user.fcm_token for user, _ in partners if getattr(user, "fcm_token", None)]
        if fcm_tokens:
            try:
                from app.core.fcm import send_multicast_push
                r_name = order.restaurant.name if order.restaurant else "Restaurant"
                send_multicast_push(
                    tokens=fcm_tokens,
                    title="New Delivery Order Available!",
                    body=f"New pickup at {r_name}. Order #{order.order_number}",
                    data={"type": "new_offer", "order_id": str(order.id)},
                )
            except Exception as e:
                logger.warning("Failed to broadcast FCM push for order %s: %s", order.id, e)
    except Exception:
        logger.exception("Broadcast dispatch failed for order %s", order_id)
    finally:
        db.close()


def accept_offer(db: Session, order_id: int, partner: User) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(404, "Order not found")
    if order.delivery_partner_id:
        from fastapi import HTTPException
        raise HTTPException(409, "This order was already accepted by another partner.")
    if order.status not in ("accepted", "ready"):
        from fastapi import HTTPException
        raise HTTPException(400, "Order not available for delivery")

    # Check if rider already has an active delivery
    has_active = (
        db.query(Order.id)
        .filter(
            Order.delivery_partner_id == partner.id,
            Order.status.in_(["accepted", "ready", "picked_up", "out_for_delivery"]),
        )
        .first()
    )
    if has_active:
        from fastapi import HTTPException
        raise HTTPException(400, "Complete the active order first before accepting a new order.")

    # Tenant check
    tenant_id = order.tenant_id or (order.restaurant.tenant_id if order.restaurant else None)
    if tenant_id is not None and partner.tenant_id is not None and partner.tenant_id != tenant_id:
        from fastapi import HTTPException
        raise HTTPException(403, "Cross-tenant assignment not allowed")

    offer = (
        db.query(DeliveryOffer)
        .filter(
            DeliveryOffer.order_id == order_id,
            DeliveryOffer.delivery_partner_id == partner.id,
            DeliveryOffer.status == "offered",
        )
        .first()
    )
    if not offer:
        from fastapi import HTTPException
        raise HTTPException(404, "No active offer for you on this order")

    now = datetime.now(timezone.utc)
    offer.status = "accepted"
    offer.responded_at = now

    # Supersede everyone else
    db.query(DeliveryOffer).filter(
        DeliveryOffer.order_id == order_id,
        DeliveryOffer.id != offer.id,
        DeliveryOffer.status == "offered",
    ).update(
        {"status": "superseded", "responded_at": now},
        synchronize_session=False,
    )

    order.delivery_partner_id = partner.id
    # Keep customer-facing status (accepted/ready); assignment is via partner id.
    db.commit()
    db.refresh(order)

    if partner.phone:
        sms.send_order_alert(partner.phone, order.order_number)
    dp_webhook.on_offer_accepted(order, partner)
    return order


def reject_offer(db: Session, order_id: int, partner: User) -> None:
    offer = (
        db.query(DeliveryOffer)
        .filter(
            DeliveryOffer.order_id == order_id,
            DeliveryOffer.delivery_partner_id == partner.id,
            DeliveryOffer.status == "offered",
        )
        .first()
    )
    if not offer:
        from fastapi import HTTPException
        raise HTTPException(404, "No active offer")
    offer.status = "rejected"
    offer.responded_at = datetime.now(timezone.utc)
    db.commit()
    dp_webhook.on_offer_rejected(order_id, partner.id)


def serialize_offer_order(db: Session, order: Order, partner: User) -> dict:
    r = order.restaurant
    r_lat = float(r.latitude) if r and r.latitude is not None else None
    r_lng = float(r.longitude) if r and r.longitude is not None else None
    c_lat = float(order.delivery_latitude) if order.delivery_latitude is not None else None
    c_lng = float(order.delivery_longitude) if order.delivery_longitude is not None else None

    profile = (
        db.query(DeliveryProfile)
        .filter(DeliveryProfile.user_id == partner.id)
        .first()
    )
    p_lat = float(profile.current_latitude) if profile and profile.current_latitude is not None else None
    p_lng = float(profile.current_longitude) if profile and profile.current_longitude is not None else None

    to_restaurant_km = None
    to_customer_km = float(order.distance_km) if order.distance_km is not None else None
    map_to_restaurant = None
    map_to_customer = None

    if p_lat is not None and r_lat is not None:
        to_restaurant_km, _ = distance_and_drive_minutes(p_lat, p_lng, r_lat, r_lng)
        map_to_restaurant = maps_embed_url(p_lat, p_lng, r_lat, r_lng)
    if p_lat is not None and c_lat is not None:
        to_customer_km, _ = distance_and_drive_minutes(p_lat, p_lng, c_lat, c_lng)
        map_to_customer = maps_embed_url(p_lat, p_lng, c_lat, c_lng)

    payout = float(
        order.delivery_partner_earning
        if order.delivery_partner_earning is not None
        else (order.delivery_fee or 0)
    )

    # Name/phone only after this partner has accepted (not on incoming offers).
    customer = getattr(order, "customer", None) if order.delivery_partner_id else None

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "restaurant": r.name if r else None,
        "restaurant_address": r.address if r else None,
        "restaurant_lat": r_lat,
        "restaurant_lng": r_lng,
        "delivery_address": order.delivery_address,
        "customer_name": customer.full_name if customer else None,
        "customer_phone": customer.phone if customer else None,
        "customer_lat": c_lat,
        "customer_lng": c_lng,
        "customer_total": float(order.total_amount or 0),
        "payout": payout,
        "distance_km_restaurant_to_customer": to_customer_km,
        "distance_km_to_restaurant": to_restaurant_km,
        "eta_minutes": order.eta_minutes,
        "map_to_restaurant": map_to_restaurant,
        "map_to_customer": map_to_customer if order.status == "picked_up" else None,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "otp_verified": bool(getattr(order, "delivery_otp_verified_at", None)),
        "cash_collected": (
            float(order.cash_collected)
            if getattr(order, "cash_collected", None) is not None
            else None
        ),
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {"name": i.name, "quantity": i.quantity, "price": float(i.actual_price or i.price)}
            for i in order.items
        ],
    }
