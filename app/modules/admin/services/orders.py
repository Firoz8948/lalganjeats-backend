from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.modules.orders.models import Order
from app.modules.orders.status_meta import ORDER_STATUSES
from app.modules.payments.breakdown import breakdown_from_order, display_payment_mode
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.payments.service import ensure_payment_settings
from app.modules.users.models import User


def _order_payment_mode(order: Order) -> dict:
    pay = display_payment_mode(order)
    return {
        "payment_mode": pay["payment_mode"],
        "payment_mode_label": pay["payment_mode_label"],
        "payment_verified": pay["payment_verified"],
        "payment_via": pay.get("payment_via"),
    }


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
    settings = ensure_payment_settings(db)
    platform_charge = float(getattr(settings, "platform_charge_rupees", 0) or 0)
    rows = []
    for order in orders:
        pay = display_payment_mode(order)
        rows.append(
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
            "payment_mode": pay["payment_mode"],
            "payment_mode_label": pay["payment_mode_label"],
            "payment_verified": pay["payment_verified"],
            "promo_code": order.promo_code,
            "promo_percent_off": (
                float(order.promo_percent_off)
                if order.promo_percent_off is not None
                else None
            ),
            "promo_free_delivery": bool(
                getattr(order, "promo_free_delivery", False)
            ),
            "admin_earning": breakdown_from_order(
                order, platform_charge=platform_charge
            ).admin.admin_profit,
            "created_at": (
                order.created_at.isoformat() if order.created_at else None
            ),
        }
        )
    return rows


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

    settings = ensure_payment_settings(db)
    platform_charge = float(getattr(settings, "platform_charge_rupees", 0) or 0)
    view = breakdown_from_order(order, platform_charge=platform_charge)
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
            platform_fee=platform_charge,
            delivery_charge=customer.delivery_charge,
            discount=customer.discount,
            delivery_payout=delivery_price,
        )
        customer = view.customer
        admin = view.admin

    pay = display_payment_mode(order, customer_total=customer.customer_total)

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "restaurant": order.restaurant.name if order.restaurant else None,
        "customer": order.customer.full_name if order.customer else None,
        "status": order.status,
        # Payment (amounts = customer total; source = prepaid / DP QR / DP cash)
        "payment_method": pay["payment_method"],
        "payment_label": pay["payment_mode_label"],
        "payment_mode": pay["payment_mode"],
        "payment_mode_label": pay["payment_mode_label"],
        "payment_verified": pay["payment_verified"],
        "payment_via": pay.get("payment_via"),
        "payment_status": pay["payment_status"],
        "online_amount": pay["online_amount"],
        "cash_collected": pay["cash_collected"],
        # Customer view
        "display_price": customer.display_price,
        "order_price": customer.display_price,  # backward-compatible alias
        "platform_fee": customer.platform_fee,
        "platform_charge": customer.platform_fee,
        "delivery_charge": customer.delivery_charge,
        "discount": customer.discount,
        "customer_total": customer.customer_total,
        # Admin view
        "hotel_price": admin.hotel_payout,
        "delivery_price": admin.delivery_payout,
        "admin_profit": admin.admin_profit,
        "is_loss": admin.is_loss,
        "menu_margin": admin.menu_margin,
        "promo_cost": admin.promo_cost,
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
                **_order_payment_mode(o),
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


from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User


def _parse_range(start_date: str | None, end_date: str | None):
    sd, ed = None, None
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            if sd.tzinfo is None:
                sd = sd.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            if ed.tzinfo is None:
                ed = ed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return sd, ed


def get_delivery_partner_earnings(
    db: Session,
    current: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Delivery partner earnings summary with settled/unsettled amounts, filtered by date range."""
    sd, ed = _parse_range(start_date, end_date)

    partner_q = db.query(User).filter(User.role == "delivery_partner")
    if current.tenant_id:
        partner_q = partner_q.filter(User.tenant_id == current.tenant_id)
    partners = partner_q.order_by(User.full_name).all()

    result = []
    for p in partners:
        base_eq = db.query(DeliveryEarning).filter(DeliveryEarning.delivery_partner_id == p.id)
        if current.tenant_id:
            base_eq = base_eq.join(Order, Order.id == DeliveryEarning.order_id).filter(Order.tenant_id == current.tenant_id)

        # Period earnings
        period_eq = base_eq
        if sd:
            period_eq = period_eq.filter(DeliveryEarning.created_at >= sd)
        if ed:
            period_eq = period_eq.filter(DeliveryEarning.created_at <= ed)

        # Settled in this period
        settled_eq = base_eq.filter(DeliveryEarning.transfer_status.in_(["settled", "completed"]))
        if sd:
            settled_eq = settled_eq.filter(
                func.coalesce(DeliveryEarning.settled_at, DeliveryEarning.created_at) >= sd
            )
        if ed:
            settled_eq = settled_eq.filter(
                func.coalesce(DeliveryEarning.settled_at, DeliveryEarning.created_at) <= ed
            )

        # Unsettled
        unsettled_eq = period_eq.filter(DeliveryEarning.transfer_status.in_(["unsettled", "pending"]))

        total_earned = period_eq.with_entities(func.coalesce(func.sum(DeliveryEarning.amount_earned), 0)).scalar() or 0.0
        total_orders = period_eq.with_entities(func.count(DeliveryEarning.id)).scalar() or 0
        unsettled_amount = unsettled_eq.with_entities(func.coalesce(func.sum(DeliveryEarning.amount_earned), 0)).scalar() or 0.0
        settled_amount = settled_eq.with_entities(func.coalesce(func.sum(DeliveryEarning.amount_earned), 0)).scalar() or 0.0

        if total_orders > 0 or total_earned > 0 or unsettled_amount > 0 or settled_amount > 0 or not sd:
            result.append({
                "partner_id": p.id,
                "name": p.full_name or p.phone or f"Partner #{p.id}",
                "phone": p.phone or "—",
                "total_earned": round(float(total_earned), 2),
                "unsettled_amount": round(float(unsettled_amount), 2),
                "settled_amount": round(float(settled_amount), 2),
                "total_orders": int(total_orders),
            })
    return result


def get_hotel_partner_earnings(
    db: Session,
    current: User,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Hotel / Restaurant partner earnings summary with settled/unsettled amounts, filtered by date range."""
    sd, ed = _parse_range(start_date, end_date)

    rest_q = db.query(Restaurant).options(joinedload(Restaurant.owner))
    if current.tenant_id:
        rest_q = rest_q.filter(Restaurant.tenant_id == current.tenant_id)
    restaurants = rest_q.order_by(Restaurant.name).all()

    result = []
    for r in restaurants:
        base_eq = db.query(RestaurantEarning).filter(RestaurantEarning.restaurant_id == r.id)
        if current.tenant_id:
            base_eq = base_eq.join(Order, Order.id == RestaurantEarning.order_id).filter(Order.tenant_id == current.tenant_id)

        # Period earnings
        period_eq = base_eq
        if sd:
            period_eq = period_eq.filter(RestaurantEarning.created_at >= sd)
        if ed:
            period_eq = period_eq.filter(RestaurantEarning.created_at <= ed)

        # Settled in this period
        settled_eq = base_eq.filter(RestaurantEarning.transfer_status.in_(["settled", "completed"]))
        if sd:
            settled_eq = settled_eq.filter(
                func.coalesce(RestaurantEarning.settled_at, RestaurantEarning.created_at) >= sd
            )
        if ed:
            settled_eq = settled_eq.filter(
                func.coalesce(RestaurantEarning.settled_at, RestaurantEarning.created_at) <= ed
            )

        # Unsettled
        unsettled_eq = period_eq.filter(RestaurantEarning.transfer_status.in_(["unsettled", "pending"]))

        total_earned = period_eq.with_entities(func.coalesce(func.sum(RestaurantEarning.amount_earned), 0)).scalar() or 0.0
        total_orders = period_eq.with_entities(func.count(RestaurantEarning.id)).scalar() or 0
        unsettled_amount = unsettled_eq.with_entities(func.coalesce(func.sum(RestaurantEarning.amount_earned), 0)).scalar() or 0.0
        settled_amount = settled_eq.with_entities(func.coalesce(func.sum(RestaurantEarning.amount_earned), 0)).scalar() or 0.0

        phone = r.phone or (r.owner.phone if r.owner else None) or "—"

        if total_orders > 0 or total_earned > 0 or unsettled_amount > 0 or settled_amount > 0 or not sd:
            result.append({
                "restaurant_id": r.id,
                "name": r.name,
                "phone": phone,
                "total_earned": round(float(total_earned), 2),
                "unsettled_amount": round(float(unsettled_amount), 2),
                "settled_amount": round(float(settled_amount), 2),
                "total_orders": int(total_orders),
            })
    return result
