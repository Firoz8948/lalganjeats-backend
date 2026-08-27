from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.orders.models import Order
from app.modules.payments.breakdown import breakdown_from_order
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.payments.service import ensure_payment_settings
from app.modules.users.models import User


def get_all_orders(db: Session, current: User):
    query = db.query(Order)
    if current.tenant_id:
        query = query.filter(Order.tenant_id == current.tenant_id)
    orders = query.order_by(Order.created_at.desc()).limit(100).all()
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
