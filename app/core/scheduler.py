"""Periodic open/close for restaurants and delivery zones."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.schedule_hours import apply_entity_schedule, now_ist
from app.modules.restaurants.models import Restaurant
from app.modules.superadmin.models import DeliveryZone

logger = logging.getLogger("lalganjeats.schedule")


def apply_restaurant_schedules(db: Session, now=None) -> int:
    """Flip restaurant is_open from configured hours. Returns changed count."""
    now = now or now_ist()
    changed = 0
    rows = (
        db.query(Restaurant)
        .filter(
            Restaurant.opening_time.isnot(None),
            Restaurant.closing_time.isnot(None),
            Restaurant.is_active == True,  # noqa: E712
        )
        .all()
    )
    for row in rows:
        new_on, new_on_date, new_off_date, did = apply_entity_schedule(
            is_on=bool(row.is_open),
            opening=row.opening_time,
            closing=row.closing_time,
            schedule_on_date=getattr(row, "schedule_opened_on", None),
            schedule_off_date=getattr(row, "schedule_closed_on", None),
            now=now,
            always_on=False,
        )
        if did:
            row.is_open = new_on
            row.schedule_opened_on = new_on_date
            row.schedule_closed_on = new_off_date
            changed += 1
    return changed


def apply_zone_schedules(db: Session, now=None) -> int:
    """Flip zone is_active from configured hours. Returns changed count."""
    now = now or now_ist()
    changed = 0
    rows = (
        db.query(DeliveryZone)
        .filter(DeliveryZone.always_available == False)  # noqa: E712
        .all()
    )
    for row in rows:
        new_on, new_on_date, new_off_date, did = apply_entity_schedule(
            is_on=bool(row.is_active),
            opening=row.opening_time,
            closing=row.closing_time,
            schedule_on_date=getattr(row, "schedule_activated_on", None),
            schedule_off_date=getattr(row, "schedule_deactivated_on", None),
            now=now,
            always_on=bool(row.always_available),
        )
        if did:
            row.is_active = new_on
            row.schedule_activated_on = new_on_date
            row.schedule_deactivated_on = new_off_date
            changed += 1
    return changed


def run_schedule_tick() -> dict:
    db = SessionLocal()
    try:
        r = apply_restaurant_schedules(db)
        z = apply_zone_schedules(db)
        if r or z:
            db.commit()
            logger.info("schedule tick: restaurants=%s zones=%s", r, z)
        else:
            db.rollback()
        return {"restaurants_changed": r, "zones_changed": z}
    except Exception:
        db.rollback()
        logger.exception("schedule tick failed")
        raise
    finally:
        db.close()
