# backend/app/modules/orders/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_customer, get_current_user
from app.modules.orders.schemas import PlaceOrderRequest, PlaceOrderResponse
from app.modules.orders import service as order_service
from app.modules.orders.models import Order

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.post("", response_model=PlaceOrderResponse)
def create_order(
    payload: PlaceOrderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_customer),
):
    return order_service.place_order(db, current_user, payload)


@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(404, "Order not found")

    role = current_user.role
    allowed = (
        (role == "customer" and order.customer_id == current_user.id)
        or (role == "delivery_partner" and order.delivery_partner_id == current_user.id)
        or (role == "restaurant_owner" and order.restaurant and order.restaurant.owner_id == current_user.id)
        or role in ("admin", "super_admin")
    )
    if not allowed:
        from fastapi import HTTPException
        raise HTTPException(403, "Not allowed")

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "delivery_fee": float(order.delivery_fee or 0),
        "delivery_address": order.delivery_address,
        "distance_km": float(order.distance_km) if order.distance_km is not None else None,
        "eta_minutes": order.eta_minutes,
        "restaurant": order.restaurant.name if order.restaurant else None,
        "customer": order.customer.full_name if order.customer else None,
        "items": [
            {"name": i.name, "quantity": i.quantity, "price": float(i.price)}
            for i in order.items
        ],
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
