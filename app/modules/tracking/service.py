# backend/app/modules/tracking/service.py
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.maps import distance_and_drive_minutes
from app.modules.users.models import User
from app.modules.getlocation import repository as loc_repo
from app.modules.tracking.schemas import LatLng, TrackOrderOut, TrackingPublicConfig
from app.modules.delivery_partner.service import serialize_public_identity
from app.modules.orders.status_meta import customer_status_meta

TRACKABLE = ("accepted", "ready", "picked_up", "delivered")


def _status_meta_for(order) -> str:
    partner = order.delivery_partner
    public = serialize_public_identity(partner) if partner else None
    bike = (public or {}).get("registered_vehicle_number") if public else None
    bike_name = (public or {}).get("bike_info") if public else None
    return customer_status_meta(
        order.status,
        restaurant_name=order.restaurant.name if order.restaurant else None,
        delivery_partner_name=partner.full_name if partner else None,
        bike_number=bike,
        bike_name=bike_name,
    )


def _coords(profile) -> tuple[float | None, float | None]:
    if profile is None:
        return None, None
    lat = profile.current_latitude
    lng = profile.current_longitude
    return (
        float(lat) if lat is not None else None,
        float(lng) if lng is not None else None,
    )


def _ll(lat, lng) -> LatLng | None:
    if lat is None or lng is None:
        return None
    try:
        return LatLng(lat=float(lat), lng=float(lng))
    except (TypeError, ValueError):
        return None


def public_config() -> TrackingPublicConfig:
    key = (settings.GOOGLE_MAPS_API_KEY or "").strip() or None
    return TrackingPublicConfig(
        google_maps_api_key=key,
        maps_enabled=bool(key),
        app_name=settings.SMS_BRAND_NAME or "LalganjEats",
        track_poll_seconds=4,
    )


def get_track_snapshot(
    db: Session,
    order_id: int,
    viewer: User,
) -> TrackOrderOut:
    """
    Rich live-tracking payload for the customer map:
    rider pin, destination, live ETA / distance.
    """
    order = loc_repo.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    allowed = False
    if viewer.role == "customer" and order.customer_id == viewer.id:
        allowed = True
    elif viewer.role == "delivery_partner" and order.delivery_partner_id == viewer.id:
        allowed = True
    elif viewer.role in ("admin", "super_admin"):
        allowed = True
    if not allowed:
        raise HTTPException(403, "Not allowed to view this order location")

    maps_key = (settings.GOOGLE_MAPS_API_KEY or "").strip() or None
    r = order.restaurant
    restaurant = _ll(
        getattr(r, "latitude", None) if r else None,
        getattr(r, "longitude", None) if r else None,
    )
    customer = _ll(order.delivery_latitude, order.delivery_longitude)

    status_meta = _status_meta_for(order)
    base = TrackOrderOut(
        available=False,
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        status_meta=status_meta,
        restaurant=restaurant,
        customer=customer,
        google_maps_api_key=maps_key,
        message=status_meta,
    )

    if not order.delivery_partner_id:
        return base

    base.delivery_partner = serialize_public_identity(order.delivery_partner)

    if order.status not in TRACKABLE:
        base.delivery_partner_id = order.delivery_partner_id
        return base

    if order.status == "delivered":
        base.available = True
        base.phase = "delivered"
        base.destination = customer
        base.eta_minutes = 0
        base.distance_km = 0
        base.eta_label = "Delivered"
        base.message = status_meta
        base.delivery_partner_id = order.delivery_partner_id
        return base

    profile = loc_repo.get_profile_by_user_id(db, order.delivery_partner_id)
    lat, lng = _coords(profile)
    base.delivery_partner_id = order.delivery_partner_id
    base.updated_at = profile.location_updated_at if profile else None

    if lat is None or lng is None:
        base.message = status_meta
        return base

    rider = LatLng(lat=lat, lng=lng)
    base.rider = rider

    if order.status in ("accepted", "ready") and order.delivery_partner_id:
        phase = "to_restaurant"
        dest = restaurant
        eta_label_prefix = "Rider reaching restaurant in"
    else:
        phase = "to_customer"
        dest = customer
        eta_label_prefix = "Rider is"

    base.phase = phase
    base.destination = dest

    if dest is None:
        base.available = True
        base.message = "Waiting for destination coordinates"
        base.eta_label = "En route"
        return base

    km, mins = distance_and_drive_minutes(rider.lat, rider.lng, dest.lat, dest.lng)
    base.distance_km = km
    base.eta_minutes = mins
    if phase == "to_customer":
        base.eta_label = f"Rider is {mins} min away"
    else:
        base.eta_label = f"{eta_label_prefix} ~{mins} min"
    base.available = True
    base.message = status_meta
    return base
