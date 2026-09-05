# backend/app/modules/promocodes/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime,
    ForeignKey, Numeric, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class PromoCode(Base):
    """
    Tenant-scoped promocode.
    channel: 'all' | 'mobile_app'
    Benefits: percent_off and/or free_delivery.
    remaining_uses decrements when an order is placed with this code.
    """
    __tablename__ = "promo_codes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_promo_tenant_code"),
    )

    id               = Column(Integer, primary_key=True, index=True)
    tenant_id        = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    code             = Column(String(40), nullable=False, index=True)
    channel          = Column(String(20), nullable=False, default="all")  # all | mobile_app
    # all = any logged-in customer, once per mobile; new_users = first order only
    audience         = Column(String(20), nullable=False, default="all")  # all | new_users
    percent_off      = Column(Numeric(5, 2), nullable=True)               # e.g. 10.00
    # percent | flat — flat uses flat_off (₹), percent uses percent_off
    discount_type    = Column(String(20), nullable=False, default="percent")
    flat_off         = Column(Numeric(10, 2), nullable=True)              # e.g. 50.00
    min_cart_value   = Column(Numeric(10, 2), nullable=True)              # e.g. 129.00
    free_delivery    = Column(Boolean, default=False, nullable=False)
    expires_at       = Column(DateTime(timezone=True), nullable=True)
    max_uses         = Column(Integer, nullable=False, default=0)         # 0 = unlimited
    remaining_uses   = Column(Integer, nullable=False, default=0)
    is_active        = Column(Boolean, default=True, nullable=False)
    is_public        = Column(Boolean, default=False, nullable=False)
    description      = Column(String(255), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    usages = relationship(
        "PromoCodeUsage", back_populates="promo",
        cascade="all, delete-orphan",
    )


class PromoCodeUsage(Base):
    """One row per order that successfully used a promocode."""
    __tablename__ = "promo_code_usages"

    id                    = Column(Integer, primary_key=True, index=True)
    promo_code_id         = Column(
        Integer, ForeignKey("promo_codes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    order_id              = Column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    user_id               = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    customer_phone        = Column(String(15), nullable=True, index=True)
    discount_amount       = Column(Numeric(10, 2), nullable=False, default=0)
    percent_off_snapshot  = Column(Numeric(5, 2), nullable=True)
    discount_type_snapshot = Column(String(20), nullable=True)
    flat_off_snapshot     = Column(Numeric(10, 2), nullable=True)
    free_delivery_applied = Column(Boolean, default=False)
    client_channel        = Column(String(20), nullable=False, default="web")
    device_id             = Column(String(64), nullable=True, index=True)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())

    promo = relationship("PromoCode", back_populates="usages")
    order = relationship("Order", back_populates="promo_usage")
    user  = relationship("User")
