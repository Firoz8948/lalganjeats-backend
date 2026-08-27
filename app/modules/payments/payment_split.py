# backend/app/modules/payments/payment_split.py
"""Order money split — delegates to payments.breakdown (single source of truth)."""
from dataclasses import dataclass

from app.modules.payments.breakdown import build_order_price_breakdown
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
    discount: float = 0,
) -> SplitResult:
    # Delivery is priced by the tenant's matching distance zone before the
    # split is calculated. Payment settings no longer define a fixed fee.
    delivery_charge = round(float(delivery_charge), 2)
    platform_charge = round(
        float(getattr(settings, "platform_charge_rupees", 0) or 0),
        2,
    )

    # Legacy % fee is kept for older order snapshots / reporting only.
    platform_fee_legacy = round(
        (settings.platform_fee_percent / 100) * display_total,
        2,
    )

    breakdown = build_order_price_breakdown(
        display_price=display_total,
        hotel_payout=actual_price_total,
        platform_fee=platform_charge,
        delivery_charge=delivery_charge,
        discount=discount,
        delivery_payout=delivery_charge,
    )
    c = breakdown.customer
    a = breakdown.admin

    return SplitResult(
        display_total=c.display_price,
        actual_price_total=round(float(actual_price_total), 2),
        delivery_charge=c.delivery_charge,
        platform_fee=platform_fee_legacy,
        platform_charge=c.platform_fee,
        hotel_earning=a.hotel_payout,
        delivery_earning=a.delivery_payout,
        admin_earning=a.admin_profit,
        customer_pays=c.customer_total,
    )
