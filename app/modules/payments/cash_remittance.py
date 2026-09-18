# backend/app/modules/payments/cash_remittance.py
"""Doorstep cash on hand + Razorpay remittance to platform."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.razorpay_service import (
    checkout_config_id,
    create_order,
    razorpay_configured,
    verify_payment_signature,
)
from app.modules.orders.models import Order
from app.modules.payments.models import CashRemittance
from app.modules.users.models import User


def parse_order_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def encode_order_ids(orders: list[Order]) -> str:
    return ",".join(str(o.id) for o in orders)


def unremitted_cash_orders(db: Session, partner_id: int) -> list[Order]:
    """Cash still with the partner until a remittance is paid (and in Revenue)."""
    return (
        db.query(Order)
        .outerjoin(CashRemittance, Order.cash_remittance_id == CashRemittance.id)
        .filter(
            Order.delivery_partner_id == partner_id,
            Order.status == "delivered",
            Order.cash_collected.isnot(None),
            Order.cash_collected > 0,
            or_(
                Order.cash_remittance_id.is_(None),
                CashRemittance.status != "paid",
            ),
        )
        .order_by(Order.updated_at.desc())
        .all()
    )


def cash_on_hand(db: Session, partner: User) -> dict:
    orders = unremitted_cash_orders(db, partner.id)
    total = round(sum(float(o.cash_collected or 0) for o in orders), 2)
    return {
        "cash_on_hand": total,
        "order_count": len(orders),
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "cash_collected": float(o.cash_collected or 0),
                "customer_total": float(o.total_amount or 0),
            }
            for o in orders
        ],
    }


def initiate_cash_remittance(db: Session, partner: User) -> dict:
    if not razorpay_configured():
        raise HTTPException(503, "Razorpay is not configured")

    # Abandoned / failed attempts leave pending remits — free those orders first.
    stale = (
        db.query(CashRemittance)
        .filter(
            CashRemittance.delivery_partner_id == partner.id,
            CashRemittance.status == "pending",
        )
        .all()
    )
    for remit in stale:
        release_pending_remittance_orders(db, remit)

    orders = unremitted_cash_orders(db, partner.id)
    amount = round(sum(float(o.cash_collected or 0) for o in orders), 2)
    if amount <= 0:
        raise HTTPException(400, "No unremitted cash to clear")

    remit = CashRemittance(
        delivery_partner_id=partner.id,
        tenant_id=partner.tenant_id,
        amount=amount,
        status="pending",
        order_ids=encode_order_ids(orders),
    )
    db.add(remit)
    db.commit()
    db.refresh(remit)

    rz_order = create_order(
        amount_rupees=amount,
        receipt=f"remit_{remit.id}",
        notes={
            "flow": "cash_remit",
            "remittance_id": str(remit.id),
            "partner_id": str(partner.id),
        },
    )
    remit.razorpay_order_id = rz_order["id"]
    db.commit()

    return {
        "remittance_id": remit.id,
        "amount": amount,
        "order_count": len(orders),
        "razorpay_order_id": rz_order["id"],
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "checkout_config_id": checkout_config_id() or None,
        "name": "LalganjEats",
        "description": f"Clear collected cash #{remit.id}",
        "prefill": {
            "name": (partner.full_name or "Partner")[:60],
            "email": (partner.email or "")[:100],
            "contact": (partner.phone or "")[:15],
        },
    }


def _attach_orders_to_paid_remittance(db: Session, remit: CashRemittance) -> None:
    ids = parse_order_ids(getattr(remit, "order_ids", None))
    if ids:
        orders = db.query(Order).filter(Order.id.in_(ids)).all()
    else:
        orders = (
            db.query(Order).filter(Order.cash_remittance_id == remit.id).all()
        )
    for o in orders:
        existing_id = o.cash_remittance_id
        if existing_id and existing_id != remit.id:
            existing = (
                db.query(CashRemittance)
                .filter(CashRemittance.id == existing_id)
                .first()
            )
            if existing and existing.status == "paid":
                continue
        o.cash_remittance_id = remit.id


def mark_remittance_paid_razorpay(
    db: Session,
    *,
    remittance_id: int,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    partner_id: int | None = None,
) -> CashRemittance:
    if not verify_payment_signature(
        razorpay_order_id, razorpay_payment_id, razorpay_signature
    ):
        raise HTTPException(400, "Invalid payment signature")

    remit = db.query(CashRemittance).filter(CashRemittance.id == remittance_id).first()
    if not remit:
        raise HTTPException(404, "Remittance not found")
    if partner_id is not None and remit.delivery_partner_id != partner_id:
        raise HTTPException(403, "Not your remittance")
    if remit.razorpay_order_id and remit.razorpay_order_id != razorpay_order_id:
        raise HTTPException(400, "Order id mismatch")

    if remit.status == "paid":
        return remit

    remit.status = "paid"
    remit.razorpay_order_id = razorpay_order_id
    remit.razorpay_payment_id = razorpay_payment_id
    remit.paid_at = datetime.now(timezone.utc)
    _attach_orders_to_paid_remittance(db, remit)
    db.commit()
    db.refresh(remit)
    return remit


def mark_remittance_paid_from_webhook(
    db: Session,
    *,
    remittance_id: int,
    razorpay_payment_id: str,
    razorpay_order_id: str | None = None,
) -> CashRemittance | None:
    remit = db.query(CashRemittance).filter(CashRemittance.id == remittance_id).first()
    if not remit:
        return None
    if remit.status == "paid":
        return remit
    remit.status = "paid"
    if razorpay_order_id:
        remit.razorpay_order_id = razorpay_order_id
    remit.razorpay_payment_id = razorpay_payment_id
    remit.paid_at = datetime.now(timezone.utc)
    _attach_orders_to_paid_remittance(db, remit)
    db.commit()
    return remit


def release_pending_remittance_orders(db: Session, remit: CashRemittance) -> None:
    """On payment failure/dismiss, unlink orders so cash stays on hand."""
    if remit.status == "paid":
        return
    orders = (
        db.query(Order).filter(Order.cash_remittance_id == remit.id).all()
    )
    for o in orders:
        o.cash_remittance_id = None
    remit.status = "failed"
    db.commit()
