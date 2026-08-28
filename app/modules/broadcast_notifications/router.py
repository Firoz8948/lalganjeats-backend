# backend/app/modules/broadcast_notifications/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_admin
from app.modules.users.models import User
from app.modules.broadcast_notifications.schemas import (
    BroadcastNotificationRequest,
    BroadcastNotificationResponse,
)
from app.modules.broadcast_notifications import service

router = APIRouter(prefix="/api/v1/broadcast-notifications", tags=["Broadcast Notifications"])


@router.post("/send", response_model=BroadcastNotificationResponse)
def send_custom_notification(
    payload: BroadcastNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin),
):
    return service.send_broadcast_notification(db, payload, current_user)
