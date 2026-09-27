# backend/app/modules/maps_usage/router.py
"""
Admin: monitor paid Google Maps usage + rider location pings.

GET /api/v1/admin/maps-usage?days=30
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_admin
from app.modules.getlocation.models import DeliveryLocationLog
from app.modules.maps_usage.models import MapsApiUsageLog, RoadDistanceCache

router = APIRouter()


@router.get("/maps-usage")
def maps_usage_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin=Depends(get_admin),
):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    day_ago = now - timedelta(days=1)

    base = db.query(MapsApiUsageLog).filter(MapsApiUsageLog.created_at >= since)

    total_calls = base.count()
    total_cost = float(
        db.query(func.coalesce(func.sum(MapsApiUsageLog.estimated_cost_inr), 0))
        .filter(MapsApiUsageLog.created_at >= since)
        .scalar()
        or 0
    )
    calls_24h = base.filter(MapsApiUsageLog.created_at >= day_ago).count()

    by_purpose = [
        {
            "purpose": purpose,
            "status": status,
            "calls": int(calls),
            "estimated_cost_inr": float(cost or 0),
        }
        for purpose, status, calls, cost in (
            db.query(
                MapsApiUsageLog.purpose,
                MapsApiUsageLog.status,
                func.count(MapsApiUsageLog.id),
                func.coalesce(func.sum(MapsApiUsageLog.estimated_cost_inr), 0),
            )
            .filter(MapsApiUsageLog.created_at >= since)
            .group_by(MapsApiUsageLog.purpose, MapsApiUsageLog.status)
            .order_by(func.count(MapsApiUsageLog.id).desc())
            .all()
        )
    ]

    day_col = func.date_trunc("day", MapsApiUsageLog.created_at)
    by_day = [
        {
            "day": day.date().isoformat() if hasattr(day, "date") else str(day),
            "calls": int(calls),
            "estimated_cost_inr": float(cost or 0),
        }
        for day, calls, cost in (
            db.query(
                day_col,
                func.count(MapsApiUsageLog.id),
                func.coalesce(func.sum(MapsApiUsageLog.estimated_cost_inr), 0),
            )
            .filter(MapsApiUsageLog.created_at >= since)
            .group_by(day_col)
            .order_by(day_col)
            .all()
        )
    ]

    recent = [
        {
            "at": row.created_at.isoformat() if row.created_at else None,
            "api": row.api_name,
            "purpose": row.purpose,
            "status": row.status,
            "origin": [row.origin_lat, row.origin_lng],
            "destination": [row.dest_lat, row.dest_lng],
            "estimated_cost_inr": float(row.estimated_cost_inr or 0),
            "error": row.error,
        }
        for row in base.order_by(MapsApiUsageLog.created_at.desc()).limit(50).all()
    ]

    cache_entries = db.query(func.count(RoadDistanceCache.id)).scalar() or 0
    cache_hits = db.query(func.coalesce(func.sum(RoadDistanceCache.hits), 0)).scalar() or 0

    pings_total = (
        db.query(func.count(DeliveryLocationLog.id))
        .filter(DeliveryLocationLog.created_at >= since)
        .scalar()
        or 0
    )
    pings_24h = (
        db.query(func.count(DeliveryLocationLog.id))
        .filter(DeliveryLocationLog.created_at >= day_ago)
        .scalar()
        or 0
    )
    pings_by_source = [
        {"source": src, "count": int(cnt)}
        for src, cnt in (
            db.query(DeliveryLocationLog.source, func.count(DeliveryLocationLog.id))
            .filter(DeliveryLocationLog.created_at >= since)
            .group_by(DeliveryLocationLog.source)
            .all()
        )
    ]

    return {
        "window_days": days,
        "cost_per_call_inr": float(getattr(settings, "MAPS_COST_PER_CALL_INR", 0.75)),
        "google": {
            "total_calls": int(total_calls),
            "calls_last_24h": int(calls_24h),
            "estimated_cost_inr": round(total_cost, 2),
            "by_purpose": by_purpose,
            "by_day": by_day,
            "recent": recent,
        },
        "road_distance_cache": {
            "entries": int(cache_entries),
            "hits": int(cache_hits),
            "estimated_saved_inr": round(
                float(cache_hits) * float(getattr(settings, "MAPS_COST_PER_CALL_INR", 0.75)), 2
            ),
        },
        "rider_location_pings": {
            "total": int(pings_total),
            "last_24h": int(pings_24h),
            "by_source": pings_by_source,
            "google_cost_inr": 0.0,
        },
    }
