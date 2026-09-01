# backend/app/modules/payments/revenue.py
"""Admin revenue ledger — money actually received by the platform."""
from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.modules.orders.models import Order
from app.modules.payments.models import CashRemittance
from app.modules.users.models import User


def compose_revenue_rows(*, orders, remittances, customer_totals: dict | None = None) -> list[dict]:
    """
    Pure composition used by admin Revenue and unit tests.

    - Prepaid online (no doorstep cash/online amounts) → customer
    - Doorstep online_collected → customer, via delivery partner
    - Unremitted cash_collected → not platform revenue yet
    - Paid cash remittance → delivery_partner / Cash payment cleared

    customer_totals: optional {order.id: customer_total} so prepaid/QR
    amounts match the admin breakdown (live ₹2 platform charge).
    """
    rows: list[dict] = []
    billed_for = customer_totals or {}

    for order in orders:
        cash = float(order.cash_collected or 0)
        online_door = float(order.online_collected or 0)
        billed = float(billed_for.get(order.id, order.total_amount or 0))
        partner = order.delivery_partner
        partner_name = partner.full_name if partner else None
        customer_name = order.customer.full_name if order.customer else None
        restaurant = order.restaurant.name if order.restaurant else None
        created = order.created_at.isoformat() if order.created_at else None

        if online_door > 0:
            collected = cash + online_door
            amount = (
                round(billed * (online_door / collected), 2)
                if cash > 0 and collected > 0
                else billed
            )
            rows.append(
                {
                    "id": f"order-online-{order.id}",
                    "source_type": "customer",
                    "payer_name": customer_name or "Customer",
                    "via": partner_name,
                    "amount": amount,
                    "method": "doorstep_online",
                    "label": (
                        f"Paid through {partner_name}"
                        if partner_name
                        else "Doorstep online"
                    ),
                    "order_number": order.order_number,
                    "restaurant": restaurant,
                    "order_status": order.status,
                    "created_at": created,
                }
            )

        if cash <= 0 and online_door <= 0:
            rows.append(
                {
                    "id": f"order-prepaid-{order.id}",
                    "source_type": "customer",
                    "payer_name": customer_name or "Customer",
                    "via": None,
                    "amount": billed,
                    "method": "prepaid_online",
                    "label": "Prepaid online",
                    "order_number": order.order_number,
                    "restaurant": restaurant,
                    "order_status": order.status,
                    "created_at": created,
                }
            )

    for remit in remittances:
        partner = remit.delivery_partner
        partner_name = partner.full_name if partner else "Delivery partner"
        order_refs = ", ".join(
            o.order_number for o in (remit.orders or []) if o.order_number
        ) or None
        rows.append(
            {
                "id": f"remit-{remit.id}",
                "source_type": "delivery_partner",
                "payer_name": partner_name,
                "via": partner_name,
                "amount": float(remit.amount or 0),
                "method": "cash_remittance",
                "label": "Cash payment cleared",
                "order_number": order_refs,
                "restaurant": None,
                "order_status": "remitted",
                "created_at": (
                    remit.paid_at.isoformat()
                    if remit.paid_at
                    else (
                        remit.created_at.isoformat() if remit.created_at else None
                    )
                ),
            }
        )

    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def build_revenue_ledger(db: Session, current: User) -> dict:
    """
    Platform money in:
    - Customer prepaid online
    - Customer doorstep online (via delivery partner portal)
    - Delivery partner cleared doorstep cash (PayU remittance)
    """
    order_q = (
        db.query(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.delivery_partner),
            joinedload(Order.restaurant),
        )
        .filter(Order.payment_status == "paid")
    )
    if current.tenant_id:
        order_q = order_q.filter(Order.tenant_id == current.tenant_id)

    orders = order_q.order_by(Order.created_at.desc()).limit(300).all()

    remit_q = (
        db.query(CashRemittance)
        .options(
            joinedload(CashRemittance.delivery_partner),
            joinedload(CashRemittance.orders),
        )
        .filter(CashRemittance.status == "paid")
    )
    if current.tenant_id:
        remit_q = remit_q.filter(CashRemittance.tenant_id == current.tenant_id)

    remits = remit_q.order_by(CashRemittance.paid_at.desc()).limit(200).all()

    from app.modules.payments.breakdown import breakdown_from_order
    from app.modules.payments.service import ensure_payment_settings

    settings = ensure_payment_settings(db)
    charge = float(getattr(settings, "platform_charge_rupees", 0) or 0)
    customer_totals = {
        o.id: breakdown_from_order(o, platform_charge=charge).customer.customer_total
        for o in orders
    }
    rows = compose_revenue_rows(
        orders=orders,
        remittances=remits,
        customer_totals=customer_totals,
    )
    total = round(sum(float(r["amount"]) for r in rows), 2)
    return {
        "total_received": total,
        "count": len(rows),
        "payments": rows,
    }
