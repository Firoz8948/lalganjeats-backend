# backend/app/modules/getlocation/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_delivery_partner
from app.modules.users.models import User
from app.modules.getlocation import schemas, service

router = APIRouter(prefix="/api/v1/getlocation", tags=["Get Location"])


@router.post("", response_model=schemas.LocationOut)
def update_location(
    payload: schemas.LocationUpdateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_delivery_partner),
):
    """Delivery partner only — push current device GPS."""
    return service.update_my_location(db, current, payload)


@router.get("/me", response_model=schemas.LocationOut)
def get_my_location(
    db: Session = Depends(get_db),
    current: User = Depends(get_delivery_partner),
):
    """Delivery partner — read own last known location."""
    return service.get_my_location(db, current)


@router.get("/order/{order_id}", response_model=schemas.LocationOut)
def get_order_location(
    order_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Partner GPS for an order. Customer map UI should use /api/v1/tracking/orders/{id}."""
    return service.get_location_for_order(db, order_id, current)
