# backend/app/modules/auth/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.auth import schemas, service

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

# ── OTP Routes (Customer / Restaurant / Delivery) ─────────
@router.post("/send-otp")
def send_otp(payload: schemas.SendOTPRequest, db: Session = Depends(get_db)):
    """
    Called from /login, /hotels, /deliverypartner login pages
    role must match the page the user is on
    """
    valid_roles = ["customer", "restaurant_owner", "delivery_partner"]
    if payload.role not in valid_roles:
        from fastapi import HTTPException
        raise HTTPException(400, "Invalid role for OTP login")

    return service.send_otp(payload.phone, payload.role, db)

@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.VerifyOTPRequest, db: Session = Depends(get_db)):
    """
    Verifies OTP + logs in (or registers) the user
    Returns JWT + redirect path
    """
    return service.verify_otp_and_login(
        phone=payload.phone,
        otp_code=payload.otp_code,
        role=payload.role,
        full_name=payload.full_name,
        accepted_legal=payload.accepted_legal,
        legal_version=payload.legal_version,
        db=db
    )

# ── Admin Login (Email + Password) ───────────────────────
@router.post("/admin-login", response_model=schemas.TokenResponse)
def admin_login(payload: schemas.AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Tenant admin login — /admin
    Email + Password (no OTP)
    """
    return service.admin_login(payload.username, payload.password, db)


# ── Super Admin Login (Email + Password) ─────────────────
@router.post("/superadmin-login", response_model=schemas.TokenResponse)
def superadmin_login(payload: schemas.AdminLoginRequest, db: Session = Depends(get_db)):
    """
    Platform super admin login — /superadmin
    Email + Password (no OTP)
    """
    return service.superadmin_login(payload.username, payload.password, db)
