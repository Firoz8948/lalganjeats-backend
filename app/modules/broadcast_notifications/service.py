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


# Which DB roles fall into each "audience bucket" we send to.
_CUSTOMER_ROLES = ("customer",)
_PARTNER_ROLES = ("restaurant_owner", "hotel_partner", "delivery_partner", "driver")


def _resolve_roles(target: str) -> list[str]:
    """Map an audience label from the admin UI to concrete DB role values."""
    t = (target or "").lower().strip()
    if t == "customers":
        return list(_CUSTOMER_ROLES)
    if t in ("restaurant_owners", "hotels", "restaurants"):
        return ["restaurant_owner", "hotel_partner"]
    if t in ("delivery_partners", "riders"):
        return ["delivery_partner", "driver"]
    # "all" / anything unrecognised → everyone
    return list(_CUSTOMER_ROLES) + list(_PARTNER_ROLES)


def send_broadcast_notification(
    db: Session,
    payload: BroadcastNotificationRequest,
    admin_user: User,
) -> BroadcastNotificationResponse:
    target = (payload.target_audience or "all").lower().strip()
    roles = _resolve_roles(target)

    users: list[User] = (
        db.query(User)
        .filter(
            User.is_active == True,  # noqa: E712
            User.fcm_token.isnot(None),
            User.role.in_(roles),
        )
        .all()
    )

    # Split by profile: customers get the SYSTEM DEFAULT sound (normal
    # notification behaviour), partners get the LOUD `order_alert` sound
    # because they must react immediately to incoming orders/offers.
    customer_tokens: list[str] = []
    partner_tokens: list[str] = []
    for u in users:
        tok = (u.fcm_token or "").strip()
        if not tok:
            continue
        if u.role in _CUSTOMER_ROLES:
            customer_tokens.append(tok)
        else:
            partner_tokens.append(tok)

    total_tokens = len(customer_tokens) + len(partner_tokens)
    if total_tokens == 0:
        return BroadcastNotificationResponse(
            success=True,
            target_audience=target,
            total_eligible_users=len(users),
            sent_count=0,
            message="No registered device tokens found for this target group.",
        )

    data_payload = {
        "type": "custom_broadcast",
        "deep_link": payload.deep_link or "/home",
    }
    if payload.image_url:
        data_payload["image_url"] = payload.image_url

    title = payload.title.strip()
    body = payload.body.strip()

    sent_count = 0
    if customer_tokens:
        sent_count += send_multicast_push(
            tokens=customer_tokens,
            title=title,
            body=body,
            data=data_payload,
            sound="default",
            channel_id="lalganjeats_alerts",
        )
    if partner_tokens:
        sent_count += send_multicast_push(
            tokens=partner_tokens,
            title=title,
            body=body,
            data=data_payload,
            # partners keep the loud alarm channel
        )

    msg = (
        f"Successfully delivered notification to {sent_count} device(s)!"
        if sent_count > 0
        else (
            f"Notification could not be delivered to {total_tokens} registered "
            "token(s). Please verify FIREBASE_CREDENTIALS_JSON in backend .env on EC2."
        )
    )

    return BroadcastNotificationResponse(
        success=sent_count > 0,
        target_audience=target,
        total_eligible_users=len(users),
        sent_count=sent_count,
        message=msg,
    )
