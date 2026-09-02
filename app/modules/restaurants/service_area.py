"""Customer service-area checks against tenant locked centre + max zone radius."""
from __future__ import annotations

from typing import Iterable

from app.core.maps import haversine_km


def matching_delivery_exception(
    exceptions: Iterable,
    customer_lat: float,
    customer_lng: float,
):
    """Return the nearest active exception whose radius contains the customer."""
    matches: list[tuple[float, object]] = []
    for exception in exceptions:
        if not getattr(exception, "is_active", False):
            continue
        lat = getattr(exception, "latitude", None)
        lng = getattr(exception, "longitude", None)
        radius_meters = getattr(exception, "radius_meters", None)
        if lat is None or lng is None or radius_meters is None:
            continue
        distance_km = haversine_km(
            float(customer_lat),
            float(customer_lng),
            float(lat),
            float(lng),
        )
        if distance_km * 1000 <= float(radius_meters):
            matches.append((distance_km, exception))
    return min(matches, key=lambda row: row[0])[1] if matches else None


def _active_zone_ranges(zones: Iterable) -> list[tuple[float, float, object]]:
    """
    Active zones as half-open km ranges: start included, end excluded.

    Explicit initial_km/final_km win. Legacy radius-only rows stack in radius
    order: 2 km then 4 km then 6 km becomes [0, 2), [2, 4), [4, 6).
    """
    explicit: list[tuple[float, float, object]] = []
    legacy: list[object] = []
    for zone in zones:
        if not getattr(zone, "is_active", False):
            continue
        initial = getattr(zone, "initial_km", None)
        final = getattr(zone, "final_km", None)
        radius = getattr(zone, "radius_km", None)
        if initial is not None and final is not None:
            start, end = float(initial), float(final)
            if end > start:
                explicit.append((start, end, zone))
        elif radius is not None:
            legacy.append(zone)
    if explicit:
        return explicit
    ranges: list[tuple[float, float, object]] = []
    prev = 0.0
    for zone in sorted(legacy, key=lambda item: float(item.radius_km)):
        end = float(zone.radius_km)
        if end > prev:
            ranges.append((prev, end, zone))
            prev = end
    return ranges


def max_active_zone_radius_km(zones: Iterable) -> float | None:
    """Largest active zone outer bound in km, or None if none configured."""
    ends = [end for _, end, _ in _active_zone_ranges(zones)]
    return max(ends) if ends else None


def delivery_charge_for_distance(
    zones: Iterable,
    distance_km: float,
) -> float | None:
    """
    Price delivery using the active zone whose range contains the distance.

    Ranges are half-open: initial km is included, final km is excluded.
    Example: 3–5 km covers 3.0, 3.1 and 4.9, but not 5.0.
    Flat zones charge their configured rate; per-km zones multiply their rate
    by the actual distance.
    """
    distance = float(distance_km)
    matches = [
        (end - start, start, zone)
        for start, end, zone in _active_zone_ranges(zones)
        if start <= distance < end
    ]
    if not matches:
        return None

    zone = sorted(matches, key=lambda row: (row[0], row[1]))[0][2]
    rate = float(getattr(zone, "rate", 0) or 0)
    if getattr(zone, "pricing_type", "flat") == "per_km":
        return round(rate * distance, 2)
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
    return distance < float(max_radius_km)
