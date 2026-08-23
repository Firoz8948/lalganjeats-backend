# backend/app/modules/orders/status_meta.py
"""Customer-facing order status labels (meta copy)."""
from __future__ import annotations

# Canonical order statuses used in the system.
ORDER_STATUSES = (
    "pending",
    "confirmed",
    "preparing",
    "ready_for_pickup",
    "assigned",
    "picked_up",
    "on_the_way",
    "delivered",
    "cancelled",
)

# Restaurant partner may only set these.
HOTEL_SETTABLE_STATUSES = (
    "confirmed",
    "preparing",
    "ready_for_pickup",
    "cancelled",
)


def customer_status_meta(
    status: str,
    *,
    restaurant_name: str | None = None,
    delivery_partner_name: str | None = None,
    bike_number: str | None = None,
) -> str:
    """Short status line shown to the customer."""
    name = (restaurant_name or "Restaurant").strip() or "Restaurant"
    partner = (delivery_partner_name or "Our delivery partner").strip()
    bike = (bike_number or "").strip()

    if status == "pending":
        return "Waiting for restaurant partner"
    if status in ("confirmed", "preparing"):
        return f"{name} is cooking your food"
    if status in ("ready_for_pickup", "assigned"):
        return "Waiting for pickup"
    if status == "picked_up":
        return "Order picked up"
    if status == "on_the_way":
        if bike:
            return (
                f"Our delivery partner, {partner}, is on the way with your "
                f"order on bike {bike}."
            )
        return f"Our delivery partner, {partner}, is on the way with your order."
    if status == "delivered":
        return "Order delivered"
    if status == "cancelled":
        return "Order cancelled"
    return status.replace("_", " ").title()
