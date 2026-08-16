# backend/app/core/security.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

# ── Password ──────────────────────────────────────────────
def hash_password(password: str) -> str:
    # Direct bcrypt — passlib+bcrypt 4.x breaks on some Python builds
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return pwd_context.verify(plain, hashed)

# ── JWT ───────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

# ── Current User ──────────────────────────────────────────
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    from app.modules.users.models import User
    payload = decode_token(credentials.credentials)
    user_id: int = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Request-scoped JWT context used by short-lived impersonation sessions.
    # These are transient attributes and are never persisted by SQLAlchemy.
    user.impersonated_by = payload.get("impersonated_by")
    user.impersonated_restaurant_id = payload.get("restaurant_id")
    user.impersonation_type = payload.get("impersonation_type")
    user.impersonation_session_id = payload.get("impersonation_session_id")
    user.impersonation_purpose = payload.get("purpose")
    # Enforce revocation/expiry on every authenticated request while impersonating
    # (covers shared endpoints such as bank-account / withdraw).
    if user.impersonated_by or user.impersonation_type or user.impersonation_session_id:
        from app.modules.admin.services.restaurants import (
            assert_live_impersonation_session,
        )

        assert_live_impersonation_session(db, user)
    return user

# ── Role Guards ───────────────────────────────────────────
def require_role(*roles: str):
    def checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(roles)}"
            )
        return current_user
    return checker

# Shortcuts
get_customer         = require_role("customer")
get_restaurant_owner = require_role("restaurant_owner")


def get_delivery_partner(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "delivery_partner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Required role: delivery_partner",
        )
    from app.modules.admin.services.restaurants import (
        assert_live_impersonation_session,
    )

    assert_live_impersonation_session(
        db,
        current_user,
        expected_type="delivery_partner",
    )
    return current_user


get_admin            = require_role("admin")          # tenant admin
get_super_admin      = require_role("super_admin")    # platform owner
get_any_staff        = require_role(
    "restaurant_owner", "delivery_partner", "admin", "super_admin"
)
