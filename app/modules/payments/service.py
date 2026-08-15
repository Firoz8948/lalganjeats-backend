# backend/app/modules/payments/service.py
from sqlalchemy.orm import Session

from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import PaymentSettings


def initial_earning_status() -> str:
    """New ledger credits require an explicit admin settlement."""
    return "unsettled"


def ensure_payment_settings(db: Session) -> PaymentSettings:
    settings = db.query(PaymentSettings).filter(PaymentSettings.id == 1).first()
    if not settings:
        settings = PaymentSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def order_display_actual_totals(order: Order) -> tuple[float, float]:
    if order.display_total is not None and order.actual_total is not None:
        return float(order.display_total), float(order.actual_total)

    display = 0.0
    actual = 0.0
    for item in order.items:
        display_price = float(item.display_price or item.price)
        actual_price = float(item.actual_price or item.price)
        display += display_price * item.quantity
        actual += actual_price * item.quantity

    if order.display_total is not None:
        display = float(order.display_total)
    if order.actual_total is not None:
        actual = float(order.actual_total)
    elif order.subtotal is not None and display == 0:
        display = float(order.subtotal)
        actual = float(order.subtotal)

    return display, actual
