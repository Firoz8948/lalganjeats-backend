from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.modules.orders.models import Order
from app.modules.orders.status_meta import LIVE_ORDER_STATUSES
from app.modules.promocodes.models import PromoCode
from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User


def active_promo_filters(tenant_id: int, now: datetime):
    return (
        PromoCode.tenant_id == tenant_id,
        PromoCode.is_active.is_(True),
        or_(PromoCode.expires_at.is_(None), PromoCode.expires_at > now),
        or_(PromoCode.max_uses == 0, PromoCode.remaining_uses > 0),
    )


def count_active_promos(
    db: Session,
    tenant_id: int,
    now: datetime | None = None,
) -> int:
    return (
        db.query(PromoCode)
        .filter(
            *active_promo_filters(
                tenant_id,
                now or datetime.now(timezone.utc),
            )
        )
        .count()
    )


def delivered_revenue_filters(tenant_id: int | None):
    filters = [Order.status == "delivered"]
    if tenant_id:
        filters.append(Order.tenant_id == tenant_id)
    return tuple(filters)


def _serialize_live_order(o: Order) -> dict:
    restaurant = o.restaurant
    partner = o.delivery_partner
    customer = o.customer
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status,
        "total_amount": float(o.total_amount or 0),
        "payment_method": o.payment_method,
        "payment_status": o.payment_status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "restaurant_name": restaurant.name if restaurant else None,
        "restaurant_phone": restaurant.phone if restaurant else None,
        "delivery_partner_name": partner.full_name if partner else None,
        "delivery_partner_phone": partner.phone if partner else None,
        "customer_name": customer.full_name if customer else None,
        "customer_phone": customer.phone if customer else None,
        "delivery_address": o.delivery_address,
    }


def get_dashboard(db: Session, current: User):
    rest_q = db.query(Restaurant)
    orders_q = db.query(Order)
    if current.tenant_id:
        rest_q = rest_q.filter(Restaurant.tenant_id == current.tenant_id)
        orders_q = orders_q.filter(Order.tenant_id == current.tenant_id)

    customer_q = db.query(func.count(func.distinct(Order.customer_id)))
    if current.tenant_id:
        customer_q = customer_q.filter(Order.tenant_id == current.tenant_id)
    total_customers = int(customer_q.scalar() or 0)
    total_restaurants = rest_q.count()
    total_orders = orders_q.count()
    delivery_q = db.query(User).filter(User.role == "delivery_partner")
    if current.tenant_id:
        delivery_q = delivery_q.filter(User.tenant_id == current.tenant_id)
    total_delivery = delivery_q.count()

    # Revenue is recognized when an order is delivered. Payment method does
    # not matter: both prepaid and successfully delivered COD orders count.
    revenue_q = db.query(func.sum(Order.total_amount)).filter(
        *delivered_revenue_filters(current.tenant_id)
    )
    revenue_row = revenue_q.scalar()
    total_revenue = float(revenue_row or 0)
    active_promos = count_active_promos(db, current.tenant_id)

    live_orders_q = (
        db.query(Order)
        .options(
            joinedload(Order.restaurant),
            joinedload(Order.delivery_partner),
            joinedload(Order.customer),
        )
        .filter(Order.status.in_(LIVE_ORDER_STATUSES))
    )
    if current.tenant_id:
        live_orders_q = live_orders_q.filter(Order.tenant_id == current.tenant_id)
    live_orders = live_orders_q.order_by(Order.created_at.desc()).limit(25).all()

    serialized = [_serialize_live_order(o) for o in live_orders]
    return {
        "stats": {
            "total_customers": total_customers,
            "total_restaurants": total_restaurants,
            "total_orders": total_orders,
            "total_delivery": total_delivery,
            "total_revenue": total_revenue,
            "active_promos": active_promos,
        },
        "live_orders": serialized,
        # Backward-compatible alias for older clients
        "recent_orders": serialized,
    }
