from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.modules.orders.models import Order
from app.modules.users.models import User


def get_all_customers(db: Session, tenant_id: int):
    customers = (
        db.query(User)
        .join(Order, Order.customer_id == User.id)
        .filter(
            User.role == "customer",
            Order.tenant_id == tenant_id,
        )
        .distinct()
        .order_by(User.created_at.desc())
        .all()
    )
    return [
        {
            "id": customer.id,
            "full_name": customer.full_name,
            "phone": customer.phone,
            "email": customer.email,
            "is_active": customer.is_active,
            "created_at": (
                customer.created_at.isoformat()
                if customer.created_at
                else None
            ),
        }
        for customer in customers
    ]


def set_customer_status(
    db: Session,
    tenant_id: int,
    customer_id: int,
    is_active: bool,
):
    customer = (
        db.query(User)
        .join(Order, Order.customer_id == User.id)
        .filter(
            User.id == customer_id,
            User.role == "customer",
            Order.tenant_id == tenant_id,
        )
        .first()
    )
    if not customer:
        raise HTTPException(404, "Customer not found for this tenant")
    customer.is_active = is_active
    db.commit()
    return {"id": customer.id, "is_active": bool(customer.is_active)}
