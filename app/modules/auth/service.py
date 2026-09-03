# backend/app/modules/auth/service.py
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.modules.auth.credentials import normalize_username
from app.modules.otp import service as otp_service
from app.modules.users.models import User

ROLE_REDIRECTS = {
    "customer":          "/",
    "restaurant_owner":  "/hotel-portal/incoming-orders",
    "delivery_partner":  "/deliverypartner",
    "admin":             "/admin/dashboard",
    "super_admin":       "/superadmin/dashboard",
}
CURRENT_LEGAL_VERSION = "2026-08-17"
PARTNER_ROLES = frozenset({"restaurant_owner", "delivery_partner"})


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
    partner_labels = {
        "delivery_partner": "Delivery partner",
        "restaurant_owner": "Restaurant partner",
    }
    if role in partner_labels and existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{partner_labels[role]} is not registered on this number. "
                "Contact the admin for listing."
            ),
        )


def _token_expiry_for_role(role: str) -> timedelta | None:
    if role in PARTNER_ROLES:
        return timedelta(minutes=settings.PARTNER_ACCESS_TOKEN_EXPIRE_MINUTES)
    return None


def _session_payload(user: User) -> dict:
    expires = _token_expiry_for_role(user.role)
    token = create_access_token(
        {"sub": str(user.id), "role": user.role},
        expires_delta=expires,
    )
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


def find_user_by_phone(phone: str, role: str, db: Session) -> User | None:
    """Finds user by User.phone, or via Restaurant.phone if role is restaurant_owner."""
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        return user

    if role == "restaurant_owner":
        from app.modules.restaurants.models import Restaurant
        digits = "".join(ch for ch in phone if ch.isdigit())
        phone_candidate = digits[-10:] if len(digits) >= 10 else phone
        restaurant = (
            db.query(Restaurant)
            .filter(or_(Restaurant.phone == phone, Restaurant.phone == phone_candidate))
            .first()
        )
        if restaurant and restaurant.owner:
            return restaurant.owner

    return None


def send_otp(phone: str, role: str, db: Session) -> dict:
    """Login OTP — delegated to otp module."""
    existing_user = find_user_by_phone(phone, role, db)
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

    user = find_user_by_phone(phone, role, db)
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
    return _session_payload(user)


def partner_password_login(
    username: str,
    password: str,
    role: str,
    accepted_legal: bool,
    legal_version: str,
    db: Session,
) -> dict:
    if role not in PARTNER_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role for partner login")

    login_id = normalize_username(username) or username.strip().lower()
    digits = "".join(ch for ch in username if ch.isdigit())
    phone_candidate = digits[-10:] if len(digits) >= 10 else None

    identity_filters = [User.username == login_id, User.phone == login_id]
    if phone_candidate:
        identity_filters.append(User.phone == phone_candidate)

    user = (
        db.query(User)
        .filter(
            User.role == role,
            User.is_active == True,  # noqa: E712
            or_(*identity_filters),
        )
        .first()
    )

    if not user and role == "restaurant_owner":
        from app.modules.restaurants.models import Restaurant
        rest_filters = [Restaurant.phone == login_id]
        if phone_candidate:
            rest_filters.append(Restaurant.phone == phone_candidate)
        restaurant = db.query(Restaurant).filter(or_(*rest_filters)).first()
        if restaurant and restaurant.owner and restaurant.owner.is_active:
            user = restaurant.owner

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Re-accept legal only when not already on current version
    if user.legal_terms_version != CURRENT_LEGAL_VERSION:
        record_legal_acceptance(
            user,
            accepted=accepted_legal,
            version=legal_version,
        )
        db.commit()
        db.refresh(user)

    return _session_payload(user)


# ── Admin Login (tenant) ──────────────────────────────────
def admin_login(username: str, password: str, db: Session) -> dict:
    u = username.strip()
    digits = "".join(c for c in u if c.isdigit())
    phone_10 = digits[-10:] if len(digits) >= 10 else None

    filters = [
        User.email.ilike(u),
        User.username.ilike(u),
        User.phone == u,
    ]
    if phone_10:
        filters.append(User.phone == phone_10)

    user = (
        db.query(User)
        .options(joinedload(User.tenant))
        .filter(
            or_(*filters),
            User.role == "admin",
            User.is_active == True,
        )
        .first()
    )

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

    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This admin account is not linked to a city. Contact super admin.",
        )

    tenant_name = user.tenant.name if user.tenant else None

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
        "redirect_to": "/admin/dashboard",
        "tenant_id": user.tenant_id,
        "tenant_name": tenant_name,
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
