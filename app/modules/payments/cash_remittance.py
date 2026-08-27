# backend/app/modules/payments/cash_remittance.py
"""Doorstep cash on hand + PayU remittance to platform."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.payu_service import (
    build_checkout_payload,
    payu_configured,
    payu_payment_url,
    verify_response_hash,
)
from app.modules.orders.models import Order
from app.modules.payments.models import CashRemittance
from app.modules.users.models import User


def unremitted_cash_orders(db: Session, partner_id: int) -> list[Order]:
    return (
        db.query(Order)
        .filter(
            Order.delivery_partner_id == partner_id,
            Order.status == "delivered",
            Order.cash_collected.isnot(None),
            Order.cash_collected > 0,
            Order.cash_remittance_id.is_(None),
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
    if not payu_configured():
        raise HTTPException(503, "PayU is not configured")

    # Abandoned / failed PayU attempts leave pending remits — free those orders first.
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

    api_base = (settings.API_PUBLIC_URL or "").rstrip("/")
    if not api_base:
        raise HTTPException(503, "API_PUBLIC_URL is not configured")

    remit = CashRemittance(
        delivery_partner_id=partner.id,
        tenant_id=partner.tenant_id,
        amount=amount,
        status="pending",
        payu_txnid=f"CR{partner.id}{uuid4().hex[:10]}".upper()[:40],
    )
    db.add(remit)
    db.flush()

    for o in orders:
        o.cash_remittance_id = remit.id
    db.commit()
    db.refresh(remit)

    fields = build_checkout_payload(
        txnid=remit.payu_txnid,
        amount=amount,
        productinfo=f"Clear collected cash #{remit.id}",
        firstname=(partner.full_name or "Partner")[:60],
        email=(partner.email or "partner@lalganjeats.com")[:100],
        phone=(partner.phone or "")[:20],
        surl=f"{api_base}/api/v1/payment/payu/success",
        furl=f"{api_base}/api/v1/payment/payu/failure",
        udf1=str(remit.id),
        udf2=f"cash-remit-{remit.id}",
        udf3="cash_remit",
    )
    return {
        "payment_url": payu_payment_url(),
        "fields": fields,
        "remittance_id": remit.id,
        "amount": amount,
        "order_count": len(orders),
    }


def mark_remittance_paid(db: Session, params: dict) -> CashRemittance | None:
    if not verify_response_hash(params):
        return None
    status = str(params.get("status") or "").lower()
    if status not in ("success", "captured"):
        return None
    if str(params.get("udf3") or "") != "cash_remit":
        return None

    remit_id = None
    try:
        remit_id = int(params.get("udf1") or 0) or None
    except (TypeError, ValueError):
        remit_id = None

    remit = None
    if remit_id:
        remit = db.query(CashRemittance).filter(CashRemittance.id == remit_id).first()
    if not remit:
        txnid = str(params.get("txnid") or "")
        if txnid:
            remit = (
                db.query(CashRemittance)
                .filter(CashRemittance.payu_txnid == txnid)
                .first()
            )
    if not remit:
        return None

    if remit.status == "paid":
        return remit

    remit.status = "paid"
    remit.payu_mihpayid = str(params.get("mihpayid") or "") or remit.payu_mihpayid
    remit.paid_at = datetime.now(timezone.utc)
    db.commit()
    return remit


def release_pending_remittance_orders(db: Session, remit: CashRemittance) -> None:
    """On PayU failure, unlink orders so cash can be remitted again."""
    if remit.status == "paid":
        return
    orders = (
        db.query(Order).filter(Order.cash_remittance_id == remit.id).all()
    )
    for o in orders:
        o.cash_remittance_id = None
    remit.status = "failed"
    db.commit()
