# backend/app/modules/banners/models.py
from sqlalchemy import Column, Integer, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class HomeBannerSlide(Base):
    __tablename__ = "home_banner_slides"

    id                = Column(Integer, primary_key=True, index=True)
    slide_number      = Column(Integer, unique=True, nullable=False)
    desktop_image_url = Column(Text)
    mobile_image_url  = Column(Text)
    is_active         = Column(Boolean, default=True, nullable=False)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())
