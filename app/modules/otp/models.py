# backend/app/modules/otp/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class OTP(Base):
    __tablename__ = "otps"

    id         = Column(Integer, primary_key=True)
    phone      = Column(String(15), nullable=False, index=True)
    otp_code   = Column(String(6), nullable=False)
    purpose    = Column(String(30), default="login")  # login | delivery
    is_used    = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
