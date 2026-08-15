from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.orders.models import Order
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.payments.payment_split import calculate_split
from app.modules.payments.service import (
    ensure_payment_settings,
    order_display_actual_totals,
)
from app.modules.users.models import User


def _order_admin_pl(order: Order, default_delivery_earning: float) -> float:
    display_total = float(order.display_total or order.subtotal or 0)
    transfer_total = float(
        order.actual_total
        if order.actual_total is not None
        else display_total
    )
    delivery_earning = float(
        order.delivery_partner_earning
        if order.delivery_partner_earning is not None
        else default_delivery_earning
    )
    return round(display_total - transfer_total - delivery_earning, 2)


def get_all_orders(db: Session, current: User):
    query = db.query(Order)
    if current.tenant_id:
        query = query.filter(Order.tenant_id == current.tenant_id)
    orders = query.order_by(Order.created_at.desc()).limit(100).all()
    default_delivery_earning = float(
        ensure_payment_settings(db).delivery_boy_per_order_earning
    )
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
            "admin_earning": _order_admin_pl(
                order,
                default_delivery_earning,
            ),
            "created_at": (
                order.created_at.isoformat() if order.created_at else None
            ),
        }
        for order in orders
    ]


def get_order_breakdown(db: Session, current: User, order_id: int):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if current.tenant_id and order.tenant_id != current.tenant_id:
        raise HTTPException(404, "Order not found")

    pay_settings = ensure_payment_settings(db)
    display_total, actual_total = order_display_actual_totals(order)
    split = calculate_split(
        display_total,
        actual_total,
        pay_settings,
        display_total,
    )

    order_price = (
        float(order.display_total)
        if order.display_total is not None
        else split.display_total
    )
    hotel_price = split.hotel_earning
    delivery_price = split.delivery_earning
    delivery_charge = (
        float(order.delivery_fee)
        if order.delivery_fee is not None
        else split.delivery_charge
    )
    platform_fee = (
        float(order.platform_fee)
        if order.platform_fee is not None
        else split.platform_fee
    )
    rest_earning = (
        db.query(RestaurantEarning)
        .filter(RestaurantEarning.order_id == order_id)
        .first()
    )
    if rest_earning is not None:
        hotel_price = float(rest_earning.amount_earned)
        if rest_earning.display_price_total is not None:
            order_price = float(rest_earning.display_price_total)
        if rest_earning.platform_fee is not None:
            platform_fee = float(rest_earning.platform_fee)

    delivery_earning = (
        db.query(DeliveryEarning)
        .filter(DeliveryEarning.order_id == order_id)
        .first()
    )
    if delivery_earning is not None:
        delivery_price = float(delivery_earning.amount_earned)

    platform_charge = round(
        order_price - hotel_price - delivery_price,
        2,
    )
    customer_total = (
        float(order.total_amount)
        if order.total_amount is not None
        else round(order_price + delivery_charge, 2)
    )

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "restaurant": order.restaurant.name if order.restaurant else None,
        "customer": order.customer.full_name if order.customer else None,
        "status": order.status,
        "order_price": round(order_price, 2),
        "delivery_charge": round(delivery_charge, 2),
        "customer_total": round(customer_total, 2),
        "hotel_price": round(hotel_price, 2),
        "delivery_price": round(delivery_price, 2),
        "platform_fee": round(platform_fee, 2),
        "platform_charge": round(platform_charge, 2),
        "admin_profit": round(platform_charge, 2),
        "is_loss": platform_charge < 0,
        "discount": float(order.discount or 0),
        "promo_code": order.promo_code,
    }
