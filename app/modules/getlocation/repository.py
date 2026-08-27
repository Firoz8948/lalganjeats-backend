# backend/app/modules/getlocation/repository.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.modules.orders.models import DeliveryProfile, Order


ACTIVE_DELIVERY_STATUSES = ("accepted", "ready", "picked_up")


def get_profile_by_user_id(db: Session, user_id: int) -> DeliveryProfile | None:
    return (
        db.query(DeliveryProfile)
        .filter(DeliveryProfile.user_id == user_id)
        .first()
    )


def get_or_create_profile(db: Session, user_id: int) -> DeliveryProfile:
    profile = get_profile_by_user_id(db, user_id)
    if profile:
        return profile
    profile = DeliveryProfile(user_id=user_id, is_online=False)
    db.add(profile)
    db.flush()
    return profile


def update_location(
    db: Session,
    profile: DeliveryProfile,
    latitude: float,
    longitude: float,
) -> DeliveryProfile:
    profile.current_latitude = latitude
    profile.current_longitude = longitude
    profile.location_updated_at = datetime.now(timezone.utc)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_order_by_id(db: Session, order_id: int) -> Order | None:
    return db.query(Order).filter(Order.id == order_id).first()


def get_active_order_for_partner(db: Session, partner_id: int) -> Order | None:
    return (
        db.query(Order)
        .filter(
            Order.delivery_partner_id == partner_id,
            Order.status.in_(ACTIVE_DELIVERY_STATUSES),
        )
        .order_by(Order.updated_at.desc().nullslast(), Order.id.desc())
        .first()
    )
