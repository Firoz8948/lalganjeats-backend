# backend/app/modules/auth/models.py
"""Auth models — OTP table lives in app.modules.otp (re-exported for compatibility)."""
from app.modules.otp.models import OTP  # noqa: F401

__all__ = ["OTP"]
