"""Customer service-area checks against tenant locked centre + max zone radius."""
from __future__ import annotations

from typing import Iterable

from app.core.maps import haversine_km


def max_active_zone_radius_km(zones: Iterable) -> float | None:
    """Largest active delivery-zone radius in km, or None if none configured."""
    radii: list[float] = []
    for zone in zones:
        if not getattr(zone, "is_active", False):
            continue
        radius = getattr(zone, "radius_km", None)
        if radius is None:
            continue
        radii.append(float(radius))
    if not radii:
        return None
    return max(radii)


def customer_within_service_area(
    customer_lat: float | None,
    customer_lng: float | None,
    center_lat: float | None,
    center_lng: float | None,
    max_radius_km: float | None,
) -> bool:
    """
    True when the customer's exact coordinates fall within the tenant's
    maximum active zone radius from the locked centre.
    """
    if (
        customer_lat is None
        or customer_lng is None
        or center_lat is None
        or center_lng is None
        or max_radius_km is None
    ):
        return False
    distance = haversine_km(
        float(customer_lat),
        float(customer_lng),
        float(center_lat),
        float(center_lng),
    )
    return distance <= float(max_radius_km)
