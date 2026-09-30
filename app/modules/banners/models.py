# backend/app/modules/banners/models.py
from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class HomeBannerSlide(Base):
    __tablename__ = "home_banner_slides"
    __table_args__ = (
        UniqueConstraint("business_category_id", "slide_number", name="uq_home_banner_category_slide"),
    )

    id                   = Column(Integer, primary_key=True, index=True)
    business_category_id = Column(Integer, ForeignKey("catalog_categories.id"), index=True)
    slide_number         = Column(Integer, nullable=False)
    desktop_image_url    = Column(Text)
    mobile_image_url     = Column(Text)
    is_active            = Column(Boolean, default=True, nullable=False)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), onupdate=func.now())
