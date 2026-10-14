# backend/app/modules/orders/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_customer, get_current_user
from app.modules.orders.schemas import (
    MultiStoreQuoteResponse,
    PlaceMultiStoreOrderRequest,
    PlaceMultiStoreOrderResponse,
    PlaceOrderRequest,
    PlaceOrderResponse,
)
from app.modules.orders import multi_store
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


@router.post("/multi-store/quote", response_model=MultiStoreQuoteResponse)
def quote_multi_store_order(
    payload: PlaceMultiStoreOrderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_customer),
):
    """Grocery-only: price a cart spanning several stores without placing it."""
    return multi_store.quote_multi_store_order(db, current_user, payload)


@router.post("/multi-store", response_model=PlaceMultiStoreOrderResponse)
def create_multi_store_order(
    payload: PlaceMultiStoreOrderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_customer),
):
    """Grocery-only: one parent order + one sub-order per store."""
    return multi_store.place_multi_store_order(db, current_user, payload)


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

    from app.modules.orders.multi_store_lifecycle import (
        order_lines,
        restaurant_label,
        shown_sub_orders,
    )

    payload = {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "is_multi_store": bool(order.is_multi_store),
        "stores": [
            {
                "order_number": s.order_number,
                "restaurant": s.restaurant.name if s.restaurant else None,
                "status": s.status,
            }
            for s in (shown_sub_orders(order) if order.is_multi_store else [])
        ],
        "refunded_amount": float(order.refunded_amount or 0),
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "delivery_fee": float(order.delivery_fee or 0),
        "packing_charge": float(getattr(order, "packing_charge", 0) or 0),
        "delivery_address": order.delivery_address,
        "distance_km": float(order.distance_km) if order.distance_km is not None else None,
        "eta_minutes": order.eta_minutes,
        "restaurant": restaurant_label(order),
        "customer": order.customer.full_name if order.customer else None,
        "items": [
            {"name": i.name, "quantity": i.quantity, "price": float(i.price)}
            for i in order_lines(order)
        ],
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
    if role == "customer" and order.customer_id == current_user.id:
        from app.modules.otp.service import customer_visible_delivery_otp
        payload["delivery_otp"] = customer_visible_delivery_otp(order)
    return payload
