# backend/app/modules/auth/schemas.py
from pydantic import BaseModel, Field
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
    accepted_legal: bool = False
    legal_version: str = ""


# ── Admin (Username + Password Flow) ─────────────────────
class AdminLoginRequest(BaseModel):
    username: str
    password: str


# ── Hotel / Delivery partner password login ───────────────
class PartnerPasswordLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=4, max_length=100)
    role: str  # 'restaurant_owner' | 'delivery_partner'
    accepted_legal: bool = False
    legal_version: str = ""


# ── Response ──────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: Optional[str]
    phone: Optional[str] = None
    redirect_to: str  # Frontend redirect path
    legal_terms_version: Optional[str] = None
