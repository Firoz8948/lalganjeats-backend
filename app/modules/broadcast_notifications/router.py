# backend/app/modules/broadcast_notifications/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin, get_current_user
from app.core.fcm import send_push_notification
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


@router.get("/debug")
def debug_notification_targets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin),
):
    """
    Diagnose why a broadcast may show 0 recipients. Returns per-role counts of
    active users vs. users with a valid FCM token registered.

    Example response:
        {
          "roles": {
            "customer":         {"active": 42, "with_token": 5},
            "restaurant_owner": {"active": 3,  "with_token": 2},
            "delivery_partner": {"active": 8,  "with_token": 7}
          },
          "total_active": 53,
          "total_with_token": 14
        }
    """
    rows = (
        db.query(User.role,
                 func.count(User.id).label("active"),
                 func.sum(
                     case(
                         (User.fcm_token.isnot(None), 1),
                         else_=0,
                     )
                 ).label("with_token"))
        .filter(User.is_active == True)  # noqa: E712
        .group_by(User.role)
        .all()
    )

    roles: dict[str, dict[str, int]] = {}
    total_active = 0
    total_with_token = 0
    for role, active, with_token in rows:
        roles[str(role or "unknown")] = {
            "active": int(active or 0),
            "with_token": int(with_token or 0),
        }
        total_active += int(active or 0)
        total_with_token += int(with_token or 0)

    return {
        "roles": roles,
        "total_active": total_active,
        "total_with_token": total_with_token,
    }


@router.post("/test-me")
def test_push_to_self(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    End-to-end validation: sends a push to the caller's own device using the
    FCM token stored on their user row. Use this to confirm the notification
    plumbing (backend → FCM → app → channel → sound) is working without
    needing an admin broadcast.
    """
    token = (current_user.fcm_token or "").strip() if current_user else ""
    if not token:
        raise HTTPException(
            status_code=400,
            detail=(
                "No FCM token on file for your account. Open the app, allow "
                "notification permission, log in, then retry. The client must "
                "have called POST /users/fcm-token (or the equivalent for your "
                "role) at least once while authenticated."
            ),
        )

    # Customers get the normal system sound; partners get the loud alarm so
    # the self-test proves the exact profile they'd hear in production.
    is_customer = (current_user.role or "").lower() == "customer"
    ok = send_push_notification(
        token=token,
        title="LalganjEats test alert",
        body=f"Hi {current_user.full_name or 'there'}, your notifications are working.",
        data={"type": "self_test", "deep_link": "/home"},
        sound="default" if is_customer else "order_alert",
        channel_id="lalganjeats_alerts" if is_customer else "lalganjeats_urgent_orders",
    )

    return {
        "delivered_to_fcm": bool(ok),
        "role": current_user.role,
        "token_prefix": token[:12] + "…",
        "hint": (
            "'delivered_to_fcm=true' means FCM accepted the message. If the "
            "phone still doesn't buzz: (1) the OS may have revoked notif "
            "permission, (2) the token may be stale (uninstall/reinstall the "
            "app), (3) battery-saver / DND may be silencing the channel, or "
            "(4) the channel `lalganjeats_urgent_orders` was not yet created "
            "on the device."
        ),
    }
