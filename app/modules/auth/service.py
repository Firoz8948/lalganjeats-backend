# backend/app/modules/auth/service.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.modules.users.models import User
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.modules.otp import service as otp_service

ROLE_REDIRECTS = {
    "customer":          "/",
    "restaurant_owner":  "/hotel-portal",
    "delivery_partner":  "/deliverypartner",
    "admin":             "/admin/dashboard",
    "super_admin":       "/superadmin/dashboard",
}
CURRENT_LEGAL_VERSION = "2026-08-17"


def record_legal_acceptance(
    user: User,
    accepted: bool,
    version: str,
    now: datetime | None = None,
) -> None:
    if not accepted or version != CURRENT_LEGAL_VERSION:
        raise HTTPException(
            status_code=400,
            detail="You must accept the current Terms, Privacy Policy and Refund Policy",
        )
    user.legal_terms_version = CURRENT_LEGAL_VERSION
    user.legal_terms_accepted_at = now or datetime.now(timezone.utc)


def ensure_role_can_register(role: str, existing_user: User | None) -> None:
    if role == "delivery_partner" and existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Delivery partner accounts must be created by your tenant admin",
        )


def send_otp(phone: str, role: str, db: Session) -> dict:
    """Login OTP — delegated to otp module."""
    existing_user = db.query(User).filter(User.phone == phone).first()
    ensure_role_can_register(role, existing_user)
    if existing_user and existing_user.role != role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This phone is registered as '{existing_user.role}'.",
        )
    if existing_user and not existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended. Contact support.",
        )
    return otp_service.send_login_otp(phone, db)


def verify_otp_and_login(
    phone: str,
    otp_code: str,
    role: str,
    full_name: str,
    accepted_legal: bool,
    legal_version: str,
    db: Session
) -> dict:
    otp_service.verify_login_otp(phone, otp_code, db)

    user = db.query(User).filter(User.phone == phone).first()
    ensure_role_can_register(role, user)

    if user:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This phone is registered as '{user.role}'. "
                       f"Please use the correct login page."
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been suspended. Contact support.",
            )
    else:
        user = User(
            phone=phone,
            full_name=full_name or f"User_{phone[-4:]}",
            role=role,
            is_active=True,
            is_verified=True
        )
        db.add(user)
    record_legal_acceptance(
        user,
        accepted=accepted_legal,
        version=legal_version,
    )
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "redirect_to": ROLE_REDIRECTS[user.role],
        "legal_terms_version": user.legal_terms_version,
    }


# ── Admin Login (tenant) ──────────────────────────────────
def admin_login(username: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(
        User.email == username,
        User.role == "admin",
        User.is_active == True
    ).first()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "tenant_id": user.tenant_id,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "full_name": user.full_name,
        "redirect_to": "/admin/dashboard"
    }


# ── Super Admin Login (platform) ──────────────────────────
def superadmin_login(username: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(
        User.email == username,
        User.role == "super_admin",
        User.is_active == True
    ).first()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = create_access_token({"sub": str(user.id), "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "full_name": user.full_name,
        "redirect_to": "/superadmin/dashboard"
    }
