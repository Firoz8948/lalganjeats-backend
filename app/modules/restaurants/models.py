# backend/app/modules/restaurants/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    Text, DateTime, DECIMAL, Time, ForeignKey, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"

    id            = Column(Integer, primary_key=True, index=True)
    owner_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id     = Column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    name          = Column(String(150), nullable=False)
    description   = Column(Text)
    phone         = Column(String(15))
    address       = Column(Text)
    city          = Column(String(100), default="Lalganj")
    pincode       = Column(String(10))
    latitude      = Column(Numeric(10, 8), nullable=True)
    longitude     = Column(Numeric(11, 8), nullable=True)
    logo_url      = Column(Text)
    list_banner_url = Column(Text)   # card cover on home / restaurants list
    banner_url    = Column(Text)     # hero above menu items on restaurant page
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
    order_items    = relationship("OrderItem", back_populates="menu_item")
