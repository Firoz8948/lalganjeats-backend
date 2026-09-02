"""Partner-facing order item lines (hotel + delivery)."""
from __future__ import annotations

from typing import Any


def _money(value: Any) -> float:
    return round(float(value or 0), 2)


def serialize_order_item(item: Any) -> dict:
    """
    Transfer-price line for hotel and delivery partners.

    Example: 250gmx1 = Kaju Katli = ₹80
    """
    qty = int(getattr(item, "quantity", 1) or 1)
    name = (getattr(item, "name", None) or "Item").strip()
    variant = (getattr(item, "variant_label", None) or "").strip()
    unit = _money(
        getattr(item, "actual_price", None)
        if getattr(item, "actual_price", None) is not None
        else getattr(item, "price", 0)
    )
    line_total = _money(unit * qty)
    prefix = f"{variant}x{qty}" if variant else f"x{qty}"
    amount = f"₹{line_total:g}"
    return {
        "name": name,
        "quantity": qty,
        "price": unit,
        "variant_label": variant or None,
        "line_total": line_total,
        "line_label": f"{prefix} = {name} = {amount}",
    }


def serialize_ordered_items(order: Any) -> list[dict]:
    """Short item list for live-order screens: 2× Butter Chicken (Full)."""
    rows: list[dict] = []
    for item in getattr(order, "items", None) or []:
        qty = int(getattr(item, "quantity", 1) or 1)
        name = (getattr(item, "name", None) or "Item").strip()
        variant = (getattr(item, "variant_label", None) or "").strip()
        label = f"{qty}× {name}"
        if variant:
            label = f"{qty}× {name} ({variant})"
        rows.append(
            {
                "name": name,
                "quantity": qty,
                "variant_label": variant or None,
                "line_label": label,
            }
        )
    return rows
