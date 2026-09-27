"""
Distance / ETA helpers.

Every paid Google call in the backend goes through `road_distance()`:

  1. DB cache lookup (road_distance_cache) keyed on coordinates rounded to
     4 dp (~11 m). Roads do not move, so hits are reused for weeks.
  2. On a miss, ONE Distance Matrix request (if a key is configured). The
     request is logged to maps_api_usage_logs with an estimated ₹ cost so
     spend can be monitored from the admin API.
  3. If Google is unavailable / errors / no key: haversine × ROAD_FACTOR.

Callers must pass a `purpose` so the usage log tells us *why* we paid.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger(__name__)

AVG_SPEED_KMH = 20.0        # city delivery fallback
COOK_BUFFER_MIN = 25
ROAD_FACTOR = 1.3           # haversine → approximate road km
CACHE_TTL_DAYS = 30
COORD_DECIMALS = 4


# ── Pure geometry ──────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def approx_road_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Free road-distance estimate (straight line × ROAD_FACTOR)."""
    return round(haversine_km(lat1, lng1, lat2, lng2) * ROAD_FACTOR, 2)


def drive_minutes_for_km(km: float) -> int:
    return max(1, math.ceil((km / AVG_SPEED_KMH) * 60))


def _cache_key(o_lat, o_lng, d_lat, d_lng) -> str:
    f = f"%.{COORD_DECIMALS}f"
    return f"{f % o_lat},{f % o_lng}|{f % d_lat},{f % d_lng}"


# ── DB cache + usage log ───────────────────────────────────────

def _cache_lookup(key: str) -> tuple[float, int] | None:
    from app.core.database import SessionLocal
    from app.modules.maps_usage.models import RoadDistanceCache

    db = SessionLocal()
    try:
        row = db.query(RoadDistanceCache).filter(RoadDistanceCache.cache_key == key).first()
        if not row:
            return None
        created = row.created_at
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS):
                return None
        row.hits = (row.hits or 0) + 1
        row.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return float(row.distance_km), int(row.duration_min)
    except Exception as exc:  # cache must never break a request
        logger.debug("road cache lookup failed: %s", exc)
        return None
    finally:
        db.close()


def _cache_store(key: str, o_lat, o_lng, d_lat, d_lng, km: float, mins: int) -> None:
    from app.core.database import SessionLocal
    from app.modules.maps_usage.models import RoadDistanceCache

    db = SessionLocal()
    try:
        row = db.query(RoadDistanceCache).filter(RoadDistanceCache.cache_key == key).first()
        now = datetime.now(timezone.utc)
        if row:
            row.distance_km = km
            row.duration_min = mins
            row.created_at = now
            row.last_used_at = now
        else:
            db.add(RoadDistanceCache(
                cache_key=key,
                origin_lat=float(o_lat), origin_lng=float(o_lng),
                dest_lat=float(d_lat), dest_lng=float(d_lng),
                distance_km=km, duration_min=mins,
                source="google", hits=0, last_used_at=now,
            ))
        db.commit()
    except Exception as exc:
        logger.debug("road cache store failed: %s", exc)
    finally:
        db.close()


def _log_usage(
    *, purpose: str, o_lat, o_lng, d_lat, d_lng,
    status: str, error: str | None = None, api_name: str = "distance_matrix",
) -> None:
    from app.core.database import SessionLocal
    from app.modules.maps_usage.models import MapsApiUsageLog

    cost = float(getattr(settings, "MAPS_COST_PER_CALL_INR", 0.75) or 0)
    db = SessionLocal()
    try:
        db.add(MapsApiUsageLog(
            api_name=api_name,
            purpose=(purpose or "unknown")[:60],
            origin_lat=float(o_lat), origin_lng=float(o_lng),
            dest_lat=float(d_lat), dest_lng=float(d_lng),
            status=status,
            error=(error or None),
            elements=1,
            estimated_cost_inr=cost,
        ))
        db.commit()
    except Exception as exc:
        logger.debug("maps usage log failed: %s", exc)
    finally:
        db.close()


# ── Google ─────────────────────────────────────────────────────

def _google_distance_km(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    purpose: str,
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
            _log_usage(purpose=purpose, o_lat=origin_lat, o_lng=origin_lng,
                       d_lat=dest_lat, d_lng=dest_lng,
                       status="zero_results", error=str(elem.get("status")))
            return None, None
        km = round(elem["distance"]["value"] / 1000.0, 2)
        mins = max(1, math.ceil(elem["duration"]["value"] / 60.0))
        _log_usage(purpose=purpose, o_lat=origin_lat, o_lng=origin_lng,
                   d_lat=dest_lat, d_lng=dest_lng, status="ok")
        return km, mins
    except Exception as exc:
        logger.warning("Google Distance Matrix failed (%s): %s", purpose, exc)
        _log_usage(purpose=purpose, o_lat=origin_lat, o_lng=origin_lng,
                   d_lat=dest_lat, d_lng=dest_lng, status="error", error=str(exc)[:500])
        return None, None


# ── Public API ─────────────────────────────────────────────────

def road_distance(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    *, purpose: str, use_google: bool = True,
) -> tuple[float, int, str]:
    """
    Returns (distance_km, drive_minutes, source) where source is
    'cache' | 'google' | 'haversine'. Never raises.
    """
    key = _cache_key(origin_lat, origin_lng, dest_lat, dest_lng)
    cached = _cache_lookup(key)
    if cached:
        return cached[0], cached[1], "cache"

    if use_google:
        g_km, g_mins = _google_distance_km(origin_lat, origin_lng, dest_lat, dest_lng, purpose)
        if g_km is not None and g_mins is not None:
            _cache_store(key, origin_lat, origin_lng, dest_lat, dest_lng, g_km, g_mins)
            return g_km, g_mins, "google"

    km = approx_road_km(origin_lat, origin_lng, dest_lat, dest_lng)
    return km, drive_minutes_for_km(km), "haversine"


def distance_and_drive_minutes(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    purpose: str = "generic",
    use_google: bool = True,
) -> tuple[float, int]:
    km, mins, _ = road_distance(
        origin_lat, origin_lng, dest_lat, dest_lng,
        purpose=purpose, use_google=use_google,
    )
    return km, mins


def estimate_customer_eta_minutes(
    restaurant_lat: float, restaurant_lng: float,
    customer_lat: float, customer_lng: float,
    cook_buffer_min: int = COOK_BUFFER_MIN,
    purpose: str = "order_placement",
) -> tuple[float, int]:
    """Returns (distance_km, total_eta_minutes including cook buffer)."""
    km, drive = distance_and_drive_minutes(
        restaurant_lat, restaurant_lng, customer_lat, customer_lng, purpose=purpose,
    )
    return km, cook_buffer_min + drive


# ── Keyless deep links (open the Google Maps APP — free) ───────

def maps_directions_url(
    dest_lat: float, dest_lng: float,
    origin_lat: float | None = None, origin_lng: float | None = None,
) -> str:
    """
    Directions deep link. Without an origin the Maps app starts from the
    device's live GPS position, which is what the rider wants.
    """
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&destination={dest_lat},{dest_lng}&travelmode=driving"
    )
    if origin_lat is not None and origin_lng is not None:
        url += f"&origin={origin_lat},{origin_lng}"
    return url


def maps_pin_url(lat: float, lng: float) -> str:
    """Show a single point in the Google Maps app."""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def maps_embed_url(origin_lat, origin_lng, dest_lat, dest_lng) -> str | None:
    """Legacy name kept for older callers — now a keyless directions link."""
    return maps_directions_url(dest_lat, dest_lng, origin_lat, origin_lng)
