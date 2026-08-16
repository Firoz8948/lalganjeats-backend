from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.orders.models import Order
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

    revenue_q = db.query(func.sum(Order.total_amount)).filter(
        Order.payment_status == "paid",
    )
    if current.tenant_id:
        revenue_q = revenue_q.filter(Order.tenant_id == current.tenant_id)
    revenue_row = revenue_q.scalar()
    total_revenue = float(revenue_row or 0)
    active_promos = count_active_promos(db, current.tenant_id)

    recent_orders_q = db.query(Order)
    if current.tenant_id:
        recent_orders_q = recent_orders_q.filter(
            Order.tenant_id == current.tenant_id
        )
    recent_orders = (
        recent_orders_q.order_by(Order.created_at.desc()).limit(10).all()
    )

    return {
        "stats": {
            "total_customers": total_customers,
            "total_restaurants": total_restaurants,
            "total_orders": total_orders,
            "total_delivery": total_delivery,
            "total_revenue": total_revenue,
            "active_promos": active_promos,
        },
        "recent_orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": float(o.total_amount),
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ],
    }
