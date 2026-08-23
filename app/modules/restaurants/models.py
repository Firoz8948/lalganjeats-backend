# backend/app/modules/restaurants/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    Text, DateTime, DECIMAL, Time, ForeignKey, Numeric, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class CatalogCategory(Base):
    __tablename__ = "catalog_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subcategories = relationship(
        "CatalogSubcategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )
    restaurants = relationship("Restaurant", back_populates="business_category")


class CatalogSubcategory(Base):
    __tablename__ = "catalog_subcategories"
    __table_args__ = (
        UniqueConstraint("category_id", "slug", name="uq_catalog_subcategory_slug"),
    )

    id = Column(Integer, primary_key=True)
    category_id = Column(
        Integer,
        ForeignKey("catalog_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    slug = Column(String(120), nullable=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    # Admin-curated subcategories shown in the customer home hero row.
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("CatalogCategory", back_populates="subcategories")
    menu_items = relationship("MenuItem", back_populates="business_subcategory")


class Restaurant(Base):
    __tablename__ = "restaurants"

    id            = Column(Integer, primary_key=True, index=True)
    owner_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id     = Column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    business_category_id = Column(
        Integer,
        ForeignKey("catalog_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name          = Column(String(150), nullable=False)
    # Public SEO URL segment: /restaurants/{slug}
    slug          = Column(String(180), nullable=True, unique=True, index=True)
    description   = Column(Text)
    phone         = Column(String(15))
    address       = Column(Text)
    city          = Column(String(100), default="Lalganj")
    pincode       = Column(String(10))
    latitude      = Column(Numeric(10, 8), nullable=True)
    longitude     = Column(Numeric(11, 8), nullable=True)
    logo_url      = Column(Text)
    list_banner_url = Column(Text)   # card cover on home / restaurants list
    banner_url    = Column(Text)     # desktop hero above menu items
    banner_mobile_url = Column(Text) # mobile hero above menu items
    is_open       = Column(Boolean, default=True)
    is_approved   = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    opening_time  = Column(Time)
    closing_time  = Column(Time)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner         = relationship("User", back_populates="restaurants",
                                 foreign_keys=[owner_id])
    tenant        = relationship("Tenant", back_populates="restaurants")
    business_category = relationship(
        "CatalogCategory", back_populates="restaurants"
    )
    categories    = relationship("MenuCategory", back_populates="restaurant",
                                 cascade="all, delete-orphan")
    menu_items    = relationship("MenuItem", back_populates="restaurant",
                                 cascade="all, delete-orphan")
    orders        = relationship("Order", back_populates="restaurant")
    earnings      = relationship("RestaurantEarning", back_populates="restaurant")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id            = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    name          = Column(String(100), nullable=False)
    sort_order    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    restaurant    = relationship("Restaurant", back_populates="categories")
    menu_items    = relationship("MenuItem", back_populates="category")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id             = Column(Integer, primary_key=True, index=True)
    restaurant_id  = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    category_id    = Column(Integer, ForeignKey("menu_categories.id"),
                            nullable=True)
    business_subcategory_id = Column(
        Integer,
        ForeignKey("catalog_subcategories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name           = Column(String(150), nullable=False)
    description    = Column(Text)
    price          = Column(DECIMAL(10, 2), nullable=False)
    actual_price   = Column(DECIMAL(10, 2), nullable=True)
    original_price = Column(DECIMAL(10, 2))
    is_veg         = Column(Boolean, default=True)
    is_available   = Column(Boolean, default=True)
    is_bestseller  = Column(Boolean, default=False)
    image_url      = Column(Text)
    sort_order     = Column(Integer, default=0)
    is_deleted     = Column(Boolean, default=False)
    deleted_at     = Column(DateTime)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    restaurant     = relationship("Restaurant", back_populates="menu_items")
    category       = relationship("MenuCategory", back_populates="menu_items")
    business_subcategory = relationship(
        "CatalogSubcategory", back_populates="menu_items"
    )
    variants       = relationship(
        "MenuItemVariant",
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="MenuItemVariant.sort_order",
    )
    order_items    = relationship("OrderItem", back_populates="menu_item")


class MenuItemVariant(Base):
    """Size/portion option for a menu item (Half, Full, etc.)."""

    __tablename__ = "menu_item_variants"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "label", name="uq_menu_item_variant_label"),
    )

    id             = Column(Integer, primary_key=True, index=True)
    menu_item_id   = Column(
        Integer, ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    label          = Column(String(40), nullable=False)
    price          = Column(DECIMAL(10, 2), nullable=False)   # display
    actual_price   = Column(DECIMAL(10, 2), nullable=False)   # seller transfer
    original_price = Column(DECIMAL(10, 2), nullable=True)    # MRP
    sort_order     = Column(Integer, default=0)
    is_available   = Column(Boolean, default=True)
    is_deleted     = Column(Boolean, default=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    menu_item      = relationship("MenuItem", back_populates="variants")
    order_items    = relationship("OrderItem", back_populates="variant")
