# backend/app/modules/getlocation/service.py
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.modules.getlocation import repository as repo
from app.modules.getlocation.schemas import LocationOut, LocationUpdateRequest


def _coords(profile) -> tuple[float | None, float | None]:
    if profile is None:
        return None, None
    lat = profile.current_latitude
    lng = profile.current_longitude
    return (float(lat) if lat is not None else None,
            float(lng) if lng is not None else None)


def update_my_location(
    db: Session,
    partner: User,
    payload: LocationUpdateRequest,
) -> LocationOut:
    profile = repo.get_or_create_profile(db, partner.id)
    profile = repo.update_location(db, profile, payload.latitude, payload.longitude)

    active = None
    if payload.order_id:
        candidate = repo.get_order_by_id(db, payload.order_id)
        if candidate and candidate.delivery_partner_id == partner.id:
            active = candidate
    if active is None:
        active = repo.get_active_order_for_partner(db, partner.id)

    source = payload.source or (
        "pickup_ping" if active and active.status in repo.TRACKING_LIVE_STATUSES else "ping"
    )
    repo.log_location(
        db, partner.id, active.id if active else None,
        payload.latitude, payload.longitude,
        accuracy_m=payload.accuracy_m, source=source,
    )
    db.commit()
    db.refresh(profile)

    out = LocationOut(
        latitude=float(profile.current_latitude),
        longitude=float(profile.current_longitude),
        updated_at=profile.location_updated_at,
        delivery_partner_id=partner.id,
        order_id=active.id if active else None,
        order_status=active.status if active else None,
        available=True,
        message="Location updated",
    )

    # Customers only see the rider after pickup; skip the broadcast otherwise.
    if active is not None and active.status in repo.TRACKING_LIVE_STATUSES:
        try:
            from app.modules.tracking.service import get_track_snapshot
            from app.modules.websocket.broadcast import publish_tracking_update

            snap = get_track_snapshot(db, active.id, partner)
            publish_tracking_update(active.id, snap.model_dump(mode="json"))
        except Exception:
            pass

    return out


def get_my_location(db: Session, partner: User) -> LocationOut:
    profile = repo.get_profile_by_user_id(db, partner.id)
    lat, lng = _coords(profile)
    active = repo.get_active_order_for_partner(db, partner.id)

    if lat is None or lng is None:
        return LocationOut(
            delivery_partner_id=partner.id,
            order_id=active.id if active else None,
            order_status=active.status if active else None,
            available=False,
            message="No location recorded yet",
        )

    return LocationOut(
        latitude=lat,
        longitude=lng,
        updated_at=profile.location_updated_at if profile else None,
        delivery_partner_id=partner.id,
        order_id=active.id if active else None,
        order_status=active.status if active else None,
        available=True,
    )


def get_location_for_order(
    db: Session,
    order_id: int,
    viewer: User,
) -> LocationOut:
    """Raw partner GPS for an order (thin endpoint). Prefer /tracking for maps UI."""
    from app.modules.tracking.service import get_track_snapshot

    track = get_track_snapshot(db, order_id, viewer)
    return LocationOut(
        latitude=track.rider.lat if track.rider else None,
        longitude=track.rider.lng if track.rider else None,
        updated_at=track.updated_at,
        delivery_partner_id=track.delivery_partner_id,
        order_id=track.order_id,
        order_status=track.order_status,
        available=track.available,
        message=track.message,
    )
