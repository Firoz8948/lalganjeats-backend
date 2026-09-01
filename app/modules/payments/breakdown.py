# backend/app/modules/payments/breakdown.py
"""
Single source of truth for order money views.

Customer view (what the buyer pays):
  display_price + platform_fee + delivery_charge − discount = customer_total

Admin view (platform P/L after partner payouts):
  customer_total − hotel_payout − delivery_payout = admin_profit

Delivery is a pass-through: customer pays it, delivery partner receives it.
Do not subtract delivery again from the food display price when computing admin profit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


def _money(value: float | int | str | None) -> float:
    return round(float(value or 0), 2)


@dataclass(frozen=True)
class CustomerPriceView:
    """What the customer sees / pays."""

    display_price: float
    platform_fee: float
    delivery_charge: float
    discount: float
    customer_total: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class AdminPriceView:
    """What admin sees for partner payouts and platform profit."""

    hotel_payout: float
    delivery_payout: float
    admin_profit: float
    is_loss: bool
    # Explains admin_profit: platform_charge + menu_margin − promo_cost
    platform_charge: float = 0.0
    menu_margin: float = 0.0
    promo_cost: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrderPriceBreakdown:
    customer: CustomerPriceView
    admin: AdminPriceView

    def as_dict(self) -> dict[str, Any]:
        return {
            "customer": self.customer.as_dict(),
            "admin": self.admin.as_dict(),
        }


def customer_price_view(
    *,
    display_price: float,
    platform_fee: float,
    delivery_charge: float,
    discount: float = 0,
) -> CustomerPriceView:
    display = _money(display_price)
    platform = _money(platform_fee)
    delivery = _money(delivery_charge)
    disc = _money(discount)
    total = _money(max(0.0, display + platform + delivery - disc))
    return CustomerPriceView(
        display_price=display,
        platform_fee=platform,
        delivery_charge=delivery,
        discount=disc,
        customer_total=total,
    )


def admin_price_view(
    *,
    customer_total: float,
    hotel_payout: float,
    delivery_payout: float,
) -> AdminPriceView:
    customer = _money(customer_total)
    hotel = _money(hotel_payout)
    delivery = _money(delivery_payout)
    profit = _money(customer - hotel - delivery)
    return AdminPriceView(
        hotel_payout=hotel,
        delivery_payout=delivery,
        admin_profit=profit,
        is_loss=profit < 0,
    )


def build_order_price_breakdown(
    *,
    display_price: float,
    hotel_payout: float,
    platform_fee: float,
    delivery_charge: float,
    discount: float = 0,
    delivery_payout: float | None = None,
) -> OrderPriceBreakdown:
    """
    Canonical breakdown used by place-order, PayU, admin UI, and promo recalc.

    delivery_payout defaults to delivery_charge (zone fee paid to rider).
    """
    customer = customer_price_view(
        display_price=display_price,
        platform_fee=platform_fee,
        delivery_charge=delivery_charge,
        discount=discount,
    )
    payout = delivery_charge if delivery_payout is None else delivery_payout
    base = admin_price_view(
        customer_total=customer.customer_total,
        hotel_payout=hotel_payout,
        delivery_payout=payout,
    )
    platform = _money(platform_fee)
    hotel = _money(hotel_payout)
    display = _money(display_price)
    promo = _money(discount)
    admin = AdminPriceView(
        hotel_payout=base.hotel_payout,
        delivery_payout=base.delivery_payout,
        admin_profit=base.admin_profit,
        is_loss=base.is_loss,
        platform_charge=platform,
        menu_margin=_money(display - hotel),
        promo_cost=promo,
    )
    return OrderPriceBreakdown(customer=customer, admin=admin)


def breakdown_from_order(order: Any) -> OrderPriceBreakdown:
    """Build views from a persisted Order row."""
    display = getattr(order, "display_total", None)
    if display is None:
        display = getattr(order, "subtotal", 0)
    hotel = getattr(order, "actual_total", None)
    if hotel is None:
        hotel = display
    platform = getattr(order, "platform_fee", 0) or 0
    delivery = getattr(order, "delivery_fee", 0) or 0
    discount = getattr(order, "discount", 0) or 0
    delivery_payout = getattr(order, "delivery_partner_earning", None)
    if delivery_payout is None:
        delivery_payout = delivery
    return build_order_price_breakdown(
        display_price=float(display or 0),
        hotel_payout=float(hotel or 0),
        platform_fee=float(platform),
        delivery_charge=float(delivery),
        discount=float(discount),
        delivery_payout=float(delivery_payout),
    )


def payment_collection_from_order(order: Any) -> dict[str, Any]:
    """How this order was paid: Online amount vs COD cash collected."""
    method = (getattr(order, "payment_method", None) or "cash").strip().lower()
    status = (getattr(order, "payment_status", None) or "").strip().lower()
    due = _money(getattr(order, "total_amount", 0))
    cash = _money(getattr(order, "cash_collected", 0))
    online = _money(getattr(order, "online_collected", 0))

    # Prepaid PayU: complete_delivery stores 0/0 and keeps method=online.
    if method == "online" and status == "paid" and cash == 0 and online == 0:
        online = due
    # Legacy COD marked paid with no cash snapshot.
    elif method in ("cash", "cod") and status == "paid" and cash == 0 and online == 0:
        cash = due

    if cash > 0 and online > 0:
        label = "Split"
    elif online > 0:
        label = "Online"
    else:
        label = "COD"

    return {
        "payment_method": method,
        "payment_label": label,
        "payment_status": status or "pending",
        "online_amount": online,
        "cash_collected": cash,
    }
