# backend/app/modules/shelves/models.py
"""Admin-curated product rows shown on a home tab (Grocery Panel)."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

DEFAULT_SECTION_BG = "#ffffff"
DEFAULT_IMAGE_BG = "#f1fbf4"
DEFAULT_CARD_BG = "#ffffff"


class ProductShelf(Base):
    __tablename__ = "product_shelves"

    id                   = Column(Integer, primary_key=True, index=True)
    business_category_id = Column(
        Integer, ForeignKey("catalog_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title                = Column(String(120), nullable=False)
    sort_order           = Column(Integer, nullable=False, default=0)
    section_bg_color     = Column(String(9), nullable=False, default=DEFAULT_SECTION_BG)
    image_bg_color       = Column(String(9), nullable=False, default=DEFAULT_IMAGE_BG)
    card_bg_color        = Column(String(9), nullable=False, default=DEFAULT_CARD_BG)
    view_all_subcategory_id = Column(
        Integer, ForeignKey("catalog_subcategories.id", ondelete="SET NULL"), nullable=True
    )
    is_active            = Column(Boolean, nullable=False, default=True)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), onupdate=func.now())

    items = relationship(
        "ProductShelfItem",
        back_populates="shelf",
        cascade="all, delete-orphan",
        order_by="ProductShelfItem.position",
    )
    view_all_subcategory = relationship("CatalogSubcategory")


class ProductShelfItem(Base):
    __tablename__ = "product_shelf_items"
    __table_args__ = (
        UniqueConstraint("shelf_id", "menu_item_id", name="uq_product_shelf_item"),
    )

    id           = Column(Integer, primary_key=True)
    shelf_id     = Column(
        Integer, ForeignKey("product_shelves.id", ondelete="CASCADE"), nullable=False, index=True
    )
    menu_item_id = Column(
        Integer, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position     = Column(Integer, nullable=False, default=0)

    shelf     = relationship("ProductShelf", back_populates="items")
    menu_item = relationship("MenuItem")
