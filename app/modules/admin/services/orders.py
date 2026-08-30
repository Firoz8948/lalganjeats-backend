from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.modules.orders.models import Order
from app.modules.orders.status_meta import ORDER_STATUSES
from app.modules.payments.breakdown import breakdown_from_order
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.payments.service import ensure_payment_settings
from app.modules.users.models import User


def get_all_orders(db: Session, current: User, status: str | None = None):
    query = db.query(Order)
    if current.tenant_id:
        query = query.filter(Order.tenant_id == current.tenant_id)

    status_key = (status or "").strip().lower()
    if status_key and status_key not in ("all", "*"):
        if status_key in ("completed", "complete"):
            status_key = "delivered"
        if status_key not in ORDER_STATUSES:
            raise HTTPException(
                400,
                f"Invalid status. Use one of: all, completed, {', '.join(ORDER_STATUSES)}",
            )
        query = query.filter(Order.status == status_key)

    orders = query.order_by(Order.created_at.desc()).limit(200).all()
    # Touch settings once so defaults exist; list P/L uses breakdown_from_order.
    ensure_payment_settings(db)
    return [
        {
            "id": order.id,
            "order_number": order.order_number,
            "customer": (
                order.customer.full_name if order.customer else None
            ),
            "restaurant": (
                order.restaurant.name if order.restaurant else None
            ),
            "status": order.status,
            "total_amount": float(order.total_amount),
            "discount": float(order.discount or 0),
            "payment_method": order.payment_method,
            "promo_code": order.promo_code,
            "promo_percent_off": (
                float(order.promo_percent_off)
                if order.promo_percent_off is not None
                else None
            ),
            "promo_free_delivery": bool(
                getattr(order, "promo_free_delivery", False)
            ),
            "admin_earning": breakdown_from_order(order).admin.admin_profit,
            "created_at": (
                order.created_at.isoformat() if order.created_at else None
            ),
        }
        for order in orders
    ]


def get_payments_received(db: Session, current: User):
    """Revenue ledger: money received by the platform."""
    from app.modules.payments.revenue import build_revenue_ledger

    return build_revenue_ledger(db, current)


def get_order_breakdown(db: Session, current: User, order_id: int):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if current.tenant_id and order.tenant_id != current.tenant_id:
        raise HTTPException(404, "Order not found")

    ensure_payment_settings(db)
    view = breakdown_from_order(order)
    customer = view.customer
    admin = view.admin

    # Prefer ledger rows when settlement amounts were recorded.
    rest_earning = (
        db.query(RestaurantEarning)
        .filter(RestaurantEarning.order_id == order_id)
        .first()
    )
    delivery_earning = (
        db.query(DeliveryEarning)
        .filter(DeliveryEarning.order_id == order_id)
        .first()
    )

    hotel_price = admin.hotel_payout
    delivery_price = admin.delivery_payout
    display_price = customer.display_price

    if rest_earning is not None:
        hotel_price = float(rest_earning.amount_earned)
        if rest_earning.display_price_total is not None:
            display_price = float(rest_earning.display_price_total)
    if delivery_earning is not None:
        delivery_price = float(delivery_earning.amount_earned)

    # Rebuild admin view if ledger amounts differ from order snapshot.
    if (
        hotel_price != admin.hotel_payout
        or delivery_price != admin.delivery_payout
        or display_price != customer.display_price
    ):
        from app.modules.payments.breakdown import build_order_price_breakdown

        view = build_order_price_breakdown(
            display_price=display_price,
            hotel_payout=hotel_price,
            platform_fee=customer.platform_fee,
            delivery_charge=customer.delivery_charge,
            discount=customer.discount,
            delivery_payout=delivery_price,
        )
        customer = view.customer
        admin = view.admin

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "restaurant": order.restaurant.name if order.restaurant else None,
        "customer": order.customer.full_name if order.customer else None,
        "status": order.status,
        # Customer view
        "display_price": customer.display_price,
        "order_price": customer.display_price,  # backward-compatible alias
        "platform_fee": customer.platform_fee,
        "delivery_charge": customer.delivery_charge,
        "discount": customer.discount,
        "customer_total": customer.customer_total,
        # Admin view
        "hotel_price": admin.hotel_payout,
        "delivery_price": admin.delivery_payout,
        "admin_profit": admin.admin_profit,
        "is_loss": admin.is_loss,
        "promo_code": order.promo_code,
        "customer_view": customer.as_dict(),
        "admin_view": admin.as_dict(),
    }


def get_completed_orders_paginated(
    db: Session, current: User, *, page: int = 1, page_size: int = 15
):
    """Paginated delivered orders with customer info."""
    query = db.query(Order).options(
        joinedload(Order.restaurant),
        joinedload(Order.delivery_partner),
        joinedload(Order.customer),
    ).filter(Order.status == "delivered")
    if current.tenant_id:
        query = query.filter(Order.tenant_id == current.tenant_id)

    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": float(o.total_amount or 0),
                "payment_method": o.payment_method,
                "payment_status": o.payment_status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "restaurant_name": o.restaurant.name if o.restaurant else None,
                "restaurant_phone": o.restaurant.phone if o.restaurant else None,
                "delivery_partner_name": o.delivery_partner.full_name if o.delivery_partner else None,
                "delivery_partner_phone": o.delivery_partner.phone if o.delivery_partner else None,
                "customer_name": o.customer.full_name if o.customer else None,
                "customer_phone": o.customer.phone if o.customer else None,
                "delivery_address": o.delivery_address,
            }
            for o in orders
        ],
    }


def get_delivery_partner_earnings(
    db: Session,
    current: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Delivery partner earnings summary, optionally filtered by date range."""
    base_q = db.query(DeliveryEarning)
    if current.tenant_id:
        base_q = base_q.join(
            Order, Order.id == DeliveryEarning.order_id
        ).filter(Order.tenant_id == current.tenant_id)

    if start_date:
        try:
            sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            base_q = base_q.filter(DeliveryEarning.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
            base_q = base_q.filter(DeliveryEarning.created_at <= ed)
        except ValueError:
            pass

    rows = (
        base_q.with_entities(
            DeliveryEarning.delivery_partner_id,
            func.sum(DeliveryEarning.amount_earned).label("total_earned"),
            func.count(DeliveryEarning.id).label("total_orders"),
        )
        .group_by(DeliveryEarning.delivery_partner_id)
        .all()
    )

    partner_ids = [r.delivery_partner_id for r in rows]
    partners = (
        db.query(User)
        .filter(User.id.in_(partner_ids))
        .all()
    ) if partner_ids else []
    partner_map = {p.id: p for p in partners}

    return [
        {
            "partner_id": r.delivery_partner_id,
            "name": partner_map[r.delivery_partner_id].full_name
                if r.delivery_partner_id in partner_map else None,
            "phone": partner_map[r.delivery_partner_id].phone
                if r.delivery_partner_id in partner_map else None,
            "total_earned": round(float(r.total_earned or 0), 2),
            "total_orders": int(r.total_orders or 0),
        }
        for r in rows
    ]
