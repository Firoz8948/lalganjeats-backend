from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.orders.models import Order
from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User


def get_dashboard(db: Session, current: User):
    rest_q = db.query(Restaurant)
    if current.tenant_id:
        rest_q = rest_q.filter(Restaurant.tenant_id == current.tenant_id)

    total_customers = db.query(User).filter(User.role == "customer").count()
    total_restaurants = rest_q.count()
    total_orders = db.query(Order).count()
    total_delivery = db.query(User).filter(
        User.role == "delivery_partner"
    ).count()
    pending_approvals = rest_q.filter(Restaurant.is_approved == False).count()

    revenue_row = db.query(func.sum(Order.total_amount)).filter(
        Order.payment_status == "paid"
    ).scalar()
    total_revenue = float(revenue_row or 0)

    recent_orders = db.query(Order).order_by(
        Order.created_at.desc()
    ).limit(10).all()

    return {
        "stats": {
            "total_customers": total_customers,
            "total_restaurants": total_restaurants,
            "total_orders": total_orders,
            "total_delivery": total_delivery,
            "pending_approvals": pending_approvals,
            "total_revenue": total_revenue,
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
