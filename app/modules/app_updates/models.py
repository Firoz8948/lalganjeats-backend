# backend/app/modules/app_updates/models.py
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class AppUpdateRelease(Base):
    __tablename__ = "app_update_releases"

    id            = Column(Integer, primary_key=True, index=True)
    app_id        = Column(String(50), nullable=False, index=True)  # customer | hotel_partner | delivery_partner
    version       = Column(String(20), nullable=False)             # e.g. "1.0.1"
    bundle_url    = Column(Text, nullable=False)                   # BunnyCDN URL or /uploads/ota/...
    checksum      = Column(String(64), nullable=True)              # SHA-256
    release_notes = Column(Text, nullable=True)
    is_mandatory  = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
