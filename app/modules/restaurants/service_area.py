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


def delivery_charge_for_distance(
    zones: Iterable,
    distance_km: float,
) -> float | None:
    """
    Price delivery using the smallest active ring containing the customer.

    Example: for 2 km and 4 km zones, a 3 km delivery uses the 4 km zone.
    Flat zones charge their configured rate; per-km zones multiply their rate
    by the actual distance.
    """
    eligible = sorted(
        (
            zone
            for zone in zones
            if getattr(zone, "is_active", False)
            and getattr(zone, "radius_km", None) is not None
            and float(zone.radius_km) >= float(distance_km)
        ),
        key=lambda zone: float(zone.radius_km),
    )
    if not eligible:
        return None

    zone = eligible[0]
    rate = float(getattr(zone, "rate", 0) or 0)
    if getattr(zone, "pricing_type", "flat") == "per_km":
        return round(rate * float(distance_km), 2)
    return round(rate, 2)


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
