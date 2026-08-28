# backend/app/modules/broadcast_notifications/service.py
import logging
from sqlalchemy.orm import Session
from app.modules.users.models import User
from app.core.fcm import send_multicast_push
from app.modules.broadcast_notifications.schemas import (
    BroadcastNotificationRequest,
    BroadcastNotificationResponse,
)

logger = logging.getLogger(__name__)


def send_broadcast_notification(
    db: Session,
    payload: BroadcastNotificationRequest,
    admin_user: User,
) -> BroadcastNotificationResponse:
    query = db.query(User).filter(User.is_active == True, User.fcm_token.isnot(None))

    target = payload.target_audience.lower().strip()
    if target == "customers":
        query = query.filter(User.role == "customer")
    elif target in ("restaurant_owners", "hotels", "restaurants"):
        query = query.filter(User.role.in_(["restaurant_owner", "hotel_partner"]))
    elif target in ("delivery_partners", "riders"):
        query = query.filter(User.role.in_(["delivery_partner", "driver"]))

    users = query.all()
    tokens = [u.fcm_token for u in users if u.fcm_token and u.fcm_token.strip()]

    if not tokens:
        return BroadcastNotificationResponse(
            success=True,
            target_audience=target,
            total_eligible_users=len(users),
            sent_count=0,
            message="No registered device tokens found for this target group."
        )

    data_payload = {
        "type": "custom_broadcast",
        "deep_link": payload.deep_link or "/home",
    }
    if payload.image_url:
        data_payload["image_url"] = payload.image_url

    sent_count = send_multicast_push(
        tokens=tokens,
        title=payload.title.strip(),
        body=payload.body.strip(),
        data=data_payload,
    )

    return BroadcastNotificationResponse(
        success=True,
        target_audience=target,
        total_eligible_users=len(users),
        sent_count=sent_count,
        message=f"Successfully delivered notification to {sent_count} device(s)!"
    )
