# backend/app/modules/payments/payment_split.py
from dataclasses import dataclass

from app.modules.payments.models import PaymentSettings


@dataclass
class SplitResult:
    display_total: float
    actual_price_total: float
    delivery_charge: float
    platform_fee: float
    platform_charge: float
    hotel_earning: float
    delivery_earning: float
    admin_earning: float
    customer_pays: float


def calculate_split(
    display_total: float,
    actual_price_total: float,
    settings: PaymentSettings,
    delivery_charge: float,
) -> SplitResult:
    # Delivery is priced by the tenant's matching distance zone before the
    # split is calculated. Payment settings no longer define a fixed fee.
    delivery_charge = round(float(delivery_charge), 2)
    platform_charge = round(
        float(getattr(settings, "platform_charge_rupees", 0) or 0),
        2,
    )

    # Legacy % fee is kept for older order snapshots only.
    platform_fee = round((settings.platform_fee_percent / 100) * display_total, 2)
    customer_pays = round(display_total + delivery_charge + platform_charge, 2)
    hotel_earning = round(actual_price_total, 2)
    # The matched tenant zone controls both the customer delivery charge and
    # the delivery partner's earning. The legacy global fixed earning is no
    # longer used for new orders.
    delivery_earning = delivery_charge

    # MRP/original price, delivery charge, and platform fee do not affect P/L.
    # Admin keeps only what remains from the displayed food price after both
    # partner obligations are deducted. A negative result is an admin loss.
    # Platform charge is collected as a customer fee and counted as admin revenue.
    admin_earning = round(
        display_total - actual_price_total - delivery_earning + platform_charge,
        2,
    )

    return SplitResult(
        display_total=round(display_total, 2),
        actual_price_total=round(actual_price_total, 2),
        delivery_charge=delivery_charge,
        platform_fee=platform_fee,
        platform_charge=platform_charge,
        hotel_earning=hotel_earning,
        delivery_earning=delivery_earning,
        admin_earning=admin_earning,
        customer_pays=customer_pays,
    )
