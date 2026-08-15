# backend/app/modules/payments/payment_split.py
from dataclasses import dataclass

from app.modules.payments.models import PaymentSettings


@dataclass
class SplitResult:
    display_total: float
    actual_price_total: float
    delivery_charge: float
    platform_fee: float
    hotel_earning: float
    delivery_earning: float
    admin_earning: float
    customer_pays: float


def calculate_split(
    display_total: float,
    actual_price_total: float,
    settings: PaymentSettings,
    order_total_for_free_delivery: float,
) -> SplitResult:
    if order_total_for_free_delivery >= settings.free_delivery_above:
        delivery_charge = 0.0
    else:
        delivery_charge = float(settings.delivery_charge)

    platform_fee = round((settings.platform_fee_percent / 100) * display_total, 2)
    customer_pays = round(display_total + delivery_charge, 2)
    hotel_earning = round(actual_price_total, 2)
    delivery_earning = float(settings.delivery_boy_per_order_earning)

    # MRP/original price, delivery charge, and platform fee do not affect P/L.
    # Admin keeps only what remains from the displayed food price after both
    # partner obligations are deducted. A negative result is an admin loss.
    admin_earning = round(
        display_total - actual_price_total - delivery_earning,
        2,
    )

    return SplitResult(
        display_total=round(display_total, 2),
        actual_price_total=round(actual_price_total, 2),
        delivery_charge=delivery_charge,
        platform_fee=platform_fee,
        hotel_earning=hotel_earning,
        delivery_earning=delivery_earning,
        admin_earning=admin_earning,
        customer_pays=customer_pays,
    )
