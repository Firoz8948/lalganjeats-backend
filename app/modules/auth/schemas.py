# backend/app/modules/auth/schemas.py
from pydantic import BaseModel
from typing import Optional

# ── Customer / Restaurant / Delivery (OTP Flow) ──────────
class SendOTPRequest(BaseModel):
    phone: str
    role: str  # 'customer' | 'restaurant_owner' | 'delivery_partner'

class VerifyOTPRequest(BaseModel):
    phone: str
    otp_code: str
    role: str
    full_name: Optional[str] = None  # Required only on first login (register)

# ── Admin (Username + Password Flow) ─────────────────────
class AdminLoginRequest(BaseModel):
    username: str
    password: str

# ── Response ──────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: Optional[str]
    phone: Optional[str] = None
    redirect_to: str  # Frontend redirect path
