# backend/app/modules/otp/service.py
"""
All OTP logic lives here:
- code generation (stub in development, random in production)
- login OTP create / send / verify
- delivery handover OTP issue / verify / clear
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.otp.models import OTP
from app.modules.otp.gateway import send_otp_sms


LOGIN_OTP_DIGITS = 6
DELIVERY_OTP_DIGITS = 4
OTP_TTL_MINUTES = 10


def is_dev() -> bool:
    return (settings.ENVIRONMENT or "").lower() == "development"


def generate_code(digits: int = LOGIN_OTP_DIGITS) -> str:
    """
    Development: fixed stub so local testing is easy.
    Production: random numeric OTP.
    """
    if is_dev():
        return "123456" if digits >= 6 else "1234"
    lo = 10 ** (digits - 1)
    hi = (10 ** digits) - 1
    return str(random.randint(lo, hi))


def _response_with_dev_hint(message: str, code: str) -> dict:
    resp = {"message": message}
    if is_dev():
        resp["dev_otp"] = code
    return resp


# ── Login OTP (otps table) ─────────────────────────────────

def send_login_otp(phone: str, db: Session) -> dict:
    """Invalidate prior unused OTPs, store new one, SMS via Renflair V1."""
    db.query(OTP).filter(
        OTP.phone == phone,
        OTP.is_used == False,
        OTP.purpose == "login",
    ).update({"is_used": True})
    db.commit()

    code = generate_code(LOGIN_OTP_DIGITS)
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    db.add(
        OTP(
            phone=phone,
            otp_code=code,
            purpose="login",
            expires_at=expires_at,
        )
    )
    db.commit()

    send_otp_sms(phone, code)
    if is_dev():
        print(f"[DEV] Login OTP for {phone}: {code}")

    return _response_with_dev_hint("OTP sent successfully", code)


def verify_login_otp(phone: str, otp_code: str, db: Session) -> None:
    """Raise 400 if invalid/expired. Marks OTP used on success."""
    otp = (
        db.query(OTP)
        .filter(
            OTP.phone == phone,
            OTP.otp_code == otp_code,
            OTP.is_used == False,
            OTP.purpose == "login",
            OTP.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )
    otp.is_used = True
    db.commit()


# ── Delivery handover OTP (stored on Order) ────────────────

def issue_delivery_otp(order, db: Session) -> dict:
    """
    Generate delivery OTP, persist on order, SMS customer phone.
    Caller must ensure order + customer phone are valid.
    """
    customer = order.customer
    if not customer or not customer.phone:
        raise HTTPException(400, "Customer phone missing")

    code = generate_code(DELIVERY_OTP_DIGITS)
    order.delivery_otp = code
    order.delivery_otp_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=OTP_TTL_MINUTES
    )
    db.commit()

    send_otp_sms(customer.phone, code)
    if is_dev():
        print(f"[DEV] Delivery OTP for order {order.order_number}: {code}")

    return _response_with_dev_hint("OTP sent to customer", code)


def verify_delivery_otp(order, otp_code: str, *, require_sent: bool = True) -> None:
    """Raise 400 if OTP missing / expired / mismatch."""
    if not order.delivery_otp:
        raise HTTPException(400, "Send OTP first" if require_sent else "Invalid OTP")
    if order.delivery_otp_expires_at:
        exp = order.delivery_otp_expires_at
        now = datetime.utcnow() if exp.tzinfo is None else datetime.now(timezone.utc)
        if exp < now:
            raise HTTPException(400, "OTP expired. Please send a new OTP.")
    if str(otp_code).strip() != str(order.delivery_otp).strip():
        raise HTTPException(400, "Invalid OTP. Please check and try again.")


def clear_delivery_otp(order, db: Session) -> None:
    order.delivery_otp = None
    order.delivery_otp_expires_at = None
    db.commit()
