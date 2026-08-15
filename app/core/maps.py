"""Distance / ETA helpers. Uses Google Distance Matrix when key is set; else haversine."""
from __future__ import annotations

import json
import logging
import math
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

AVG_SPEED_KMH = 20.0  # city delivery fallback
COOK_BUFFER_MIN = 25


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def _google_distance_km(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
) -> tuple[float | None, int | None]:
    key = (settings.GOOGLE_MAPS_API_KEY or "").strip()
    if not key:
        return None, None
    params = urlencode({
        "origins": f"{origin_lat},{origin_lng}",
        "destinations": f"{dest_lat},{dest_lng}",
        "mode": "driving",
        "key": key,
    })
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{params}"
    try:
        with urlopen(Request(url), timeout=12) as resp:
            data = json.loads(resp.read().decode())
        elem = data["rows"][0]["elements"][0]
        if elem.get("status") != "OK":
            return None, None
        km = round(elem["distance"]["value"] / 1000.0, 2)
        mins = max(1, math.ceil(elem["duration"]["value"] / 60.0))
        return km, mins
    except Exception as exc:
        logger.warning("Google Distance Matrix failed: %s", exc)
        return None, None


def distance_and_drive_minutes(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
) -> tuple[float, int]:
    g_km, g_mins = _google_distance_km(origin_lat, origin_lng, dest_lat, dest_lng)
    if g_km is not None and g_mins is not None:
        return g_km, g_mins
    km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    mins = max(1, math.ceil((km / AVG_SPEED_KMH) * 60))
    return km, mins


def estimate_customer_eta_minutes(
    restaurant_lat: float, restaurant_lng: float,
    customer_lat: float, customer_lng: float,
    cook_buffer_min: int = COOK_BUFFER_MIN,
) -> tuple[float, int]:
    """Returns (distance_km, total_eta_minutes including cook buffer)."""
    km, drive = distance_and_drive_minutes(
        restaurant_lat, restaurant_lng, customer_lat, customer_lng
    )
    return km, cook_buffer_min + drive


def maps_embed_url(origin_lat, origin_lng, dest_lat, dest_lng) -> str | None:
    key = (settings.GOOGLE_MAPS_API_KEY or "").strip()
    if not key:
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={origin_lat},{origin_lng}"
            f"&destination={dest_lat},{dest_lng}"
            "&travelmode=driving"
        )
    return (
        "https://www.google.com/maps/embed/v1/directions"
        f"?key={key}&origin={origin_lat},{origin_lng}"
        f"&destination={dest_lat},{dest_lng}&mode=driving"
    )
