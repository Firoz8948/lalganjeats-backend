# backend/app/modules/delivery/router.py
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_delivery_partner
from app.modules.orders.models import Order, DeliveryProfile, DeliveryOffer
from app.modules.delivery import dispatch
from app.modules.delivery import webhook as dp_webhook
from app.modules.otp import service as otp_service

router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery Partner"])


def _ensure_profile(db: Session, user_id: int) -> DeliveryProfile:
    profile = db.query(DeliveryProfile).filter(DeliveryProfile.user_id == user_id).first()
    if not profile:
        profile = DeliveryProfile(user_id=user_id, is_online=False)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


# ── Dashboard ──────────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    profile = _ensure_profile(db, current_user.id)
    today = datetime.utcnow().date()

    today_orders = db.query(Order).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == "delivered",
        func.date(Order.updated_at) == today,
    ).count()

    today_earn = db.query(
        func.coalesce(func.sum(Order.delivery_partner_earning), 0)
    ).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == "delivered",
        func.date(Order.updated_at) == today,
    ).scalar()

    active = (
        db.query(Order)
        .filter(
            Order.delivery_partner_id == current_user.id,
            Order.status.in_(["assigned", "picked_up", "on_the_way"]),
        )
        .order_by(Order.updated_at.desc())
        .first()
    )

    offers = (
        db.query(DeliveryOffer)
        .filter(
            DeliveryOffer.delivery_partner_id == current_user.id,
            DeliveryOffer.status == "offered",
        )
        .order_by(DeliveryOffer.offered_at.desc())
        .all()
    )
    available = []
    for off in offers:
        o = off.order
        if not o or o.delivery_partner_id:
            continue
        available.append(dispatch.serialize_offer_order(db, o, current_user))

    return {
        "profile": {
            "is_online": profile.is_online,
            "full_name": current_user.full_name,
            "phone": current_user.phone,
            "total_earnings": float(profile.total_earnings or 0),
            "has_location": profile.current_latitude is not None,
        },
        "today": {
            "orders": today_orders,
            "earnings": float(today_earn or 0),
        },
        "active_order": (
            dispatch.serialize_offer_order(db, active, current_user) if active else None
        ),
        "available_orders": available,
    }


@router.patch("/toggle-online")
def toggle_online(
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    profile = _ensure_profile(db, current_user.id)
    profile.is_online = not profile.is_online
    db.commit()
    return {"is_online": profile.is_online}


@router.patch("/orders/{order_id}/accept")
def accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = dispatch.accept_offer(db, order_id, current_user)
    return {
        "message": "Order accepted",
        "order_number": order.order_number,
        "status": order.status,
        "order": dispatch.serialize_offer_order(db, order, current_user),
    }


@router.patch("/orders/{order_id}/reject")
def reject_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    dispatch.reject_offer(db, order_id, current_user)
    return {"message": "Offer rejected"}


@router.patch("/orders/{order_id}/picked-up")
def mark_picked_up(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status == "assigned",
    ).first()
    if not order:
        raise HTTPException(404, "Order not found or not assigned to you")
    order.status = "picked_up"
    db.commit()
    dp_webhook.on_picked_up(order, current_user)
    return {
        "status": order.status,
        "order": dispatch.serialize_offer_order(db, order, current_user),
    }


@router.patch("/orders/{order_id}/on-the-way")
def mark_on_the_way(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status == "picked_up",
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")
    order.status = "on_the_way"
    db.commit()
    return {"status": order.status}


@router.post("/orders/{order_id}/send-otp")
def send_delivery_otp(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status.in_(["picked_up", "on_the_way"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")
    return otp_service.issue_delivery_otp(order, db)


class VerifyOtpBody(BaseModel):
    otp: str


@router.post("/orders/{order_id}/verify-otp")
def verify_delivery_otp(
    order_id: int,
    body: VerifyOtpBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status.in_(["picked_up", "on_the_way"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")
    otp_service.verify_delivery_otp(order, body.otp)
    return {"verified": True}


class CompleteBody(BaseModel):
    collection_method: str  # cash | online
    otp: str


@router.post("/orders/{order_id}/complete")
def complete_delivery(
    order_id: int,
    body: CompleteBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    if body.collection_method not in ("cash", "online"):
        raise HTTPException(400, "collection_method must be cash or online")

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status.in_(["picked_up", "on_the_way"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")

    otp_service.verify_delivery_otp(order, body.otp)

    order.status = "delivered"
    order.payment_status = "paid"
    if body.collection_method == "online":
        order.payment_method = order.payment_method or "online"

    payout = float(
        order.delivery_partner_earning
        if order.delivery_partner_earning is not None
        else (order.delivery_fee or 0)
    )
    profile = _ensure_profile(db, current_user.id)
    profile.total_earnings = float(profile.total_earnings or 0) + payout

    order.delivery_otp = None
    order.delivery_otp_expires_at = None
    db.commit()

    # COD orders and online orders assigned after payment both need complete,
    # idempotent partner ledger rows once the delivery partner is known.
    from app.modules.payments.router import process_payment_split
    process_payment_split(order.id)

    dp_webhook.on_delivered(order, current_user)

    return {
        "message": "Order delivered",
        "status": "delivered",
        "collection_method": body.collection_method,
        "online_stub": body.collection_method == "online",
    }


@router.get("/orders")
def list_my_orders(
    filter: str = "all",
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    q = db.query(Order).filter(Order.delivery_partner_id == current_user.id)
    if filter == "active":
        q = q.filter(Order.status.in_(["assigned", "picked_up", "on_the_way"]))
    elif filter == "delivered":
        q = q.filter(Order.status == "delivered")
    orders = q.order_by(Order.created_at.desc()).limit(100).all()
    return [dispatch.serialize_offer_order(db, o, current_user) for o in orders]


@router.get("/earnings")
def get_earnings(
    filter: str = "today",
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    query = db.query(Order).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == "delivered",
    )
    now = datetime.utcnow()
    if filter == "today":
        query = query.filter(func.date(Order.updated_at) == now.date())
    elif filter == "week":
        query = query.filter(Order.updated_at >= now - timedelta(days=7))
    elif filter == "month":
        query = query.filter(Order.updated_at >= now - timedelta(days=30))

    orders = query.order_by(Order.updated_at.desc()).all()
    total = sum(
        float(o.delivery_partner_earning if o.delivery_partner_earning is not None else (o.delivery_fee or 0))
        for o in orders
    )
    return {
        "filter": filter,
        "total_orders": len(orders),
        "total_earned": total,
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "restaurant": o.restaurant.name if o.restaurant else None,
                "earning": float(
                    o.delivery_partner_earning
                    if o.delivery_partner_earning is not None
                    else (o.delivery_fee or 0)
                ),
                "delivered_at": o.updated_at.isoformat() if o.updated_at else None,
            }
            for o in orders
        ],
    }
