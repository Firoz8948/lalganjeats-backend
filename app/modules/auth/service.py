# backend/app/modules/auth/service.py
from datetime import datetime
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


def send_otp(phone: str, role: str, db: Session) -> dict:
    """Login OTP — delegated to otp module."""
    return otp_service.send_login_otp(phone, db)


def verify_otp_and_login(
    phone: str,
    otp_code: str,
    role: str,
    full_name: str,
    db: Session
) -> dict:
    otp_service.verify_login_otp(phone, otp_code, db)

    user = db.query(User).filter(User.phone == phone).first()

    if user:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This phone is registered as '{user.role}'. "
                       f"Please use the correct login page."
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
        "redirect_to": ROLE_REDIRECTS[user.role]
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
