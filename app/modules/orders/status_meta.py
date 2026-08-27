# backend/app/modules/orders/status_meta.py
"""Customer-facing order status labels (meta copy)."""
from __future__ import annotations

# Canonical order statuses (customer POV — also stored on orders.status).
ORDER_STATUSES = (
    "pending",
    "accepted",
    "ready",
    "picked_up",
    "delivered",
    "cancelled",
)

# Restaurant partner may only set these.
HOTEL_SETTABLE_STATUSES = (
    "accepted",
    "ready",
    "cancelled",
)

# In-flight orders (admin Live Orders, etc.)
LIVE_ORDER_STATUSES = (
    "pending",
    "accepted",
    "ready",
    "picked_up",
)

# Customer progress strip (excludes cancelled).
CUSTOMER_STATUS_FLOW = (
    "pending",
    "accepted",
    "ready",
    "picked_up",
    "delivered",
)

STATUS_SHORT_LABELS = {
    "pending": "PEND",
    "accepted": "ACCEPT",
    "ready": "READY",
    "picked_up": "PICKED",
    "delivered": "✓",
    "cancelled": "CANC",
}


def customer_status_meta(
    status: str,
    *,
    restaurant_name: str | None = None,
    delivery_partner_name: str | None = None,
    bike_number: str | None = None,
    bike_name: str | None = None,
) -> str:
    """Short status line shown to the customer."""
    partner = (delivery_partner_name or "Our delivery partner").strip()
    bike_no = (bike_number or "").strip()
    bike_nm = (bike_name or "").strip()

    if status == "pending":
        return "Waiting for restaurant to accept the order"
    if status == "accepted":
        return "Your food is getting cooked"
    if status == "ready":
        return "Waiting for pickup"
    if status == "picked_up":
        bike_bits = " ".join(p for p in (bike_nm, bike_no) if p).strip()
        if bike_bits:
            return (
                f"{partner} with his {bike_bits} on the way to deliver the order"
            )
        return f"{partner} on the way to deliver the order"
    if status == "delivered":
        return "Order delivered"
    if status == "cancelled":
        return "Order cancelled"
    return status.replace("_", " ").title()
