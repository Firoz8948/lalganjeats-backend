# backend/app/modules/tracking/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.modules.users.models import User
from app.modules.tracking import service, schemas

router = APIRouter(prefix="/api/v1/tracking", tags=["Tracking"])


@router.get("/config", response_model=schemas.TrackingPublicConfig)
def tracking_config():
    """Maps key + poll interval for the customer tracking UI."""
    return service.public_config()


@router.get("/orders/{order_id}", response_model=schemas.TrackOrderOut)
def track_order(
    order_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Live tracking snapshot for the customer map.
    Poll every 3–5 seconds from the app.
    """
    return service.get_track_snapshot(db, order_id, current)
