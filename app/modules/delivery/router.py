# backend/app/modules/delivery/router.py
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_delivery_partner
from app.modules.orders.models import Order, DeliveryProfile, DeliveryOffer
from app.modules.delivery import dispatch
from app.modules.delivery import webhook as dp_webhook
from app.modules.delivery.actives import merge_active_order_payloads
from app.modules.otp import service as otp_service

router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery Partner"])

IST = timezone(timedelta(hours=5, minutes=30))


def _ist_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def _parse_day(value: str | None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD")
    return datetime.now(IST).date()


def _order_delivered_col():
    return func.coalesce(Order.delivery_otp_verified_at, Order.created_at)


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

    if profile.is_online:
        dispatch.ensure_open_offers_for_partner(db, current_user)

    delivered_col = _order_delivered_col()
    today_start, today_end = _ist_day_bounds(datetime.now(IST).date())

    today_orders = db.query(Order).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == "delivered",
        delivered_col >= today_start,
        delivered_col < today_end,
    ).count()

    today_earn = db.query(
        func.coalesce(
            func.sum(
                func.coalesce(Order.delivery_partner_earning, Order.delivery_fee, 0)
            ),
            0,
        )
    ).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == "delivered",
        delivered_col >= today_start,
        delivered_col < today_end,
    ).scalar()

    actives = (
        db.query(Order)
        .options(
            joinedload(Order.restaurant),
            joinedload(Order.items),
            joinedload(Order.customer),
        )
        .filter(
            Order.delivery_partner_id == current_user.id,
            Order.status.in_(["accepted", "ready", "picked_up", "out_for_delivery"]),
        )
        .order_by(Order.created_at.asc(), Order.id.asc())
        .all()
    )
    serialized_actives = merge_active_order_payloads(
        [
            dispatch.serialize_offer_order(db, order, current_user)
            for order in actives
        ]
    )

    available = []
    offers = (
        db.query(DeliveryOffer)
        .filter(
            DeliveryOffer.delivery_partner_id == current_user.id,
            DeliveryOffer.status == "offered",
        )
        .order_by(DeliveryOffer.offered_at.desc())
        .all()
    )
    for off in offers:
        o = off.order
        if not o or o.delivery_partner_id or o.status == "cancelled":
            continue
        available.append(dispatch.serialize_offer_order(db, o, current_user))

    return {
        "profile": {
            "is_online": profile.is_online,
            "full_name": current_user.full_name,
            "phone": current_user.phone,
            "total_earnings": float(profile.total_earnings or 0),
            "has_location": profile.current_latitude is not None,
            "allow_multiple_orders": bool(
                getattr(profile, "allow_multiple_orders", False)
            ),
        },
        "today": {
            "orders": today_orders,
            "earnings": float(today_earn or 0),
        },
        "active_order": serialized_actives[0] if serialized_actives else None,
        "active_orders": serialized_actives,
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
    if profile.is_online:
        dispatch.ensure_open_offers_for_partner(db, current_user)
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
        Order.status == "ready",
    ).first()
    if not order:
        raise HTTPException(
            404,
            "Order not found, not assigned to you, or restaurant has not marked Ready yet",
        )
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
    """Legacy no-op: picked_up already means on the way for the customer."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status == "picked_up",
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")
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
        Order.status.in_(["picked_up", "out_for_delivery"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found or not in transit")
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
        Order.status.in_(["picked_up", "out_for_delivery"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found or not in transit")
    otp_service.verify_delivery_otp(order, body.otp)
    order.delivery_otp_verified_at = datetime.utcnow()
    db.commit()
    return {"verified": True, "message": "OTP verified successfully"}


class CollectionPaymentBody(BaseModel):
    online_amount: float


# ── Razorpay Payment Link doorstep collection ──────────────
# The DP taps "Show UPI QR" → we create a Razorpay Payment Link and return
# its short_url for the QR. Customer pays → webhook / status poll marks paid.
# encodes into a QR the customer scans.  Their phone opens the URL → we render
# Razorpay Payment Link → customer scans QR (short_url) → webhook marks
# `collection_online_paid_at`. DP app polls /collect-online/status.
@router.post("/orders/{order_id}/collect-online/initiate")
def initiate_online_collection(
    order_id: int,
    body: CollectionPaymentBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    import time

    from app.core.razorpay_service import create_payment_link, razorpay_configured

    if body.online_amount <= 0:
        raise HTTPException(400, "online_amount must be greater than 0")
    if not razorpay_configured():
        raise HTTPException(503, "Online payments are not configured")

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status.in_(["picked_up", "out_for_delivery"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found or not in transit")
    if (order.payment_status or "").lower() == "paid":
        raise HTTPException(400, "Order is already paid")

    due = float(order.total_amount or 0)
    amount = round(float(body.online_amount), 2)
    if amount > due + 0.01:
        raise HTTPException(400, "online_amount exceeds order total")

    expire_by = int(time.time()) + 15 * 60
    customer = order.customer
    link = create_payment_link(
        amount_rupees=amount,
        description=f"LalganjEats order {order.order_number}",
        notes={
            "flow": "collect_at_door",
            "order_id": str(order.id),
            "order_number": order.order_number or "",
        },
        customer={
            "name": ((customer.full_name if customer else None) or "Customer")[:50],
            "contact": ((customer.phone if customer else None) or "")[:15],
        } if customer and (customer.phone or customer.full_name) else None,
        expire_by=expire_by,
    )
    plink_id = str(link.get("id") or "")
    short_url = str(link.get("short_url") or "")
    if not plink_id or not short_url:
        raise HTTPException(502, "Could not create Razorpay payment link")

    order.collection_txnid = plink_id
    order.collection_amount = amount
    order.collection_initiated_at = datetime.utcnow()
    order.collection_online_paid_at = None
    db.commit()

    expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    return {
        "txnid": plink_id,
        "amount": amount,
        "qr_url": short_url,
        "payment_page_url": short_url,
        "expires_at": expires_at,
    }


@router.get("/orders/{order_id}/collect-online/status")
def get_online_collection_status(
    order_id: int,
    txnid: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")

    paid = bool(order.collection_online_paid_at) and (order.collection_txnid or "") == txnid

    # Fallback: poll Razorpay Payment Link if webhook is delayed.
    if not paid and txnid and (order.collection_txnid or "") == txnid:
        try:
            from app.core.razorpay_service import fetch_payment_link

            link = fetch_payment_link(txnid)
            status = str(link.get("status") or "").lower()
            if status == "paid":
                payments = link.get("payments") or []
                pay_id = None
                if payments and isinstance(payments[0], dict):
                    pay_id = payments[0].get("payment_id") or payments[0].get("id")
                order.collection_online_paid_at = datetime.utcnow()
                order.online_collected = float(order.collection_amount or 0)
                if pay_id:
                    order.razorpay_payment_id = str(pay_id)
                db.commit()
                paid = True
        except Exception:
            pass

    return {
        "txnid": txnid,
        "paid": paid,
        "amount": float(order.collection_amount or 0) if paid else 0.0,
        "paid_at": order.collection_online_paid_at.isoformat() if paid and order.collection_online_paid_at else None,
    }


class CompleteBody(BaseModel):
    otp: str
    cash_amount: float = 0
    online_amount: float = 0
    # Razorpay Payment Link id (plink_…). Required when online_amount > 0.
    collection_txnid: str | None = None


@router.post("/orders/{order_id}/complete")
def complete_delivery(
    order_id: int,
    body: CompleteBody,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.delivery_partner_id == current_user.id,
        Order.status.in_(["picked_up", "out_for_delivery"]),
    ).first()
    if not order:
        raise HTTPException(404, "Order not found")

    otp_service.verify_delivery_otp(order, body.otp)
    if not order.delivery_otp_verified_at:
        order.delivery_otp_verified_at = datetime.utcnow()

    already_paid = (order.payment_status or "").lower() == "paid"
    due = round(float(order.total_amount or 0), 2)
    cash = round(float(body.cash_amount or 0), 2)
    online = round(float(body.online_amount or 0), 2)

    if cash < 0 or online < 0:
        raise HTTPException(400, "Amounts cannot be negative")

    if already_paid:
        cash, online = 0.0, 0.0
    else:
        if abs((cash + online) - due) > 0.05:
            raise HTTPException(
                400,
                f"Cash + online must equal order total ₹{due:g}",
            )
        if online > 0:
            if not body.collection_txnid:
                raise HTTPException(
                    400,
                    "Online collection requires a verified Razorpay payment. "
                    "Show the UPI QR to the customer first and wait for it to be paid.",
                )
            if (order.collection_txnid or "") != body.collection_txnid:
                raise HTTPException(400, "Collection txnid mismatch")
            if not order.collection_online_paid_at:
                raise HTTPException(
                    400,
                    "Razorpay collection has not been confirmed yet",
                )
            expected = round(float(order.collection_amount or 0), 2)
            if abs(expected - online) > 0.05:
                raise HTTPException(
                    400,
                    f"Online amount ({online}) doesn't match verified collection ({expected})",
                )

    order.status = "delivered"
    order.payment_status = "paid"
    order.cash_collected = cash if cash > 0 else None
    order.online_collected = online if online > 0 else None
    if already_paid:
        pass  # keep original payment_method
    elif cash > 0 and online > 0:
        order.payment_method = "split"
    elif online > 0:
        order.payment_method = "online"
    else:
        order.payment_method = "cash"

    payout = float(
        order.delivery_partner_earning
        if order.delivery_partner_earning is not None
        else (order.delivery_fee or 0)
    )
    profile = _ensure_profile(db, current_user.id)
    profile.total_earnings = float(profile.total_earnings or 0) + payout

    order.delivery_otp = None
    order.delivery_otp_expires_at = None
    order.delivery_otp_verified_at = order.delivery_otp_verified_at or datetime.utcnow()
    db.commit()

    from app.modules.payments.router import process_payment_split
    process_payment_split(order.id)

    dp_webhook.on_delivered(order, current_user)

    return {
        "message": "Order delivered",
        "status": "delivered",
        "cash_collected": cash,
        "online_collected": online,
        "already_paid": already_paid,
    }


@router.get("/orders")
def list_my_orders(
    filter: str = "today",
    date: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    q = db.query(Order).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status != "cancelled",
    )
    delivered_col = _order_delivered_col()
    if filter == "active":
        q = q.filter(Order.status.in_(["accepted", "ready", "picked_up"]))
    elif filter in ("today", "history", "delivered"):
        q = q.filter(Order.status == "delivered")
        if filter == "today":
            start, end = _ist_day_bounds(_parse_day(date))
            q = q.filter(delivered_col >= start, delivered_col < end)
        elif date:
            start, end = _ist_day_bounds(_parse_day(date))
            q = q.filter(delivered_col >= start, delivered_col < end)

    page_size = 10
    page = max(1, int(page or 1))
    total = int(q.count() or 0)
    total_pages = (total + page_size - 1) // page_size if total else 0
    if page > total_pages > 0:
        page = total_pages

    orders = (
        q.options(
            joinedload(Order.items),
            joinedload(Order.restaurant),
            joinedload(Order.customer),
        )
        .order_by(delivered_col.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "items": [
            dispatch.serialize_offer_order(db, o, current_user, for_list=True)
            for o in orders
        ],
    }


@router.get("/earnings")
def get_earnings(
    filter: str = "today",
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    delivered_col = _order_delivered_col()
    query = db.query(Order).filter(
        Order.delivery_partner_id == current_user.id,
        Order.status == "delivered",
    )
    now_ist = datetime.now(IST)
    if filter == "today":
        start, end = _ist_day_bounds(now_ist.date())
        query = query.filter(delivered_col >= start, delivered_col < end)
    elif filter == "week":
        start = (now_ist - timedelta(days=7)).astimezone(timezone.utc)
        query = query.filter(delivered_col >= start)
    elif filter == "month":
        start = (now_ist - timedelta(days=30)).astimezone(timezone.utc)
        query = query.filter(delivered_col >= start)

    orders = query.order_by(delivered_col.desc(), Order.id.desc()).all()
    total = sum(
        float(o.delivery_partner_earning if o.delivery_partner_earning is not None else (o.delivery_fee or 0))
        for o in orders
    )
    cash_total = sum(float(o.cash_collected or 0) for o in orders)
    return {
        "filter": filter,
        "total_orders": len(orders),
        "total_earned": total,
        "cash_collected": cash_total,
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
                "cash_collected": float(o.cash_collected or 0),
                "payment_method": o.payment_method,
                "delivered_at": (
                    (o.delivery_otp_verified_at or o.created_at).isoformat()
                    if (o.delivery_otp_verified_at or o.created_at)
                    else None
                ),
            }
            for o in orders
        ],
    }


@router.get("/cash-on-hand")
def get_cash_on_hand(
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    from app.modules.payments.cash_remittance import cash_on_hand

    return cash_on_hand(db, current_user)


@router.get("/cash-remittances")
def list_cash_remittances(
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    from app.modules.payments.history import cash_remittance_history

    return cash_remittance_history(db, current_user.id, page)


@router.post("/cash-remit/initiate")
def initiate_cash_remit(
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    from app.modules.payments.cash_remittance import initiate_cash_remittance

    return initiate_cash_remittance(db, current_user)


class DpFcmTokenUpdate(BaseModel):
    fcm_token: str


@router.post("/fcm-token")
def update_delivery_fcm_token(
    payload: DpFcmTokenUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_delivery_partner),
):
    current_user.fcm_token = payload.fcm_token.strip()
    db.commit()
    return {"status": "ok"}
