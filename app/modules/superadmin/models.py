# backend/app/modules/superadmin/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, Text, DateTime,
    ForeignKey, Numeric, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Tenant(Base):
    """
    One tenant = one city/centre operator (admin account).
    Centre lat/long is set by super admin and locked for the tenant admin.
    """
    __tablename__ = "tenants"

    id                       = Column(Integer, primary_key=True, index=True)
    name                     = Column(String(150), nullable=False)
    slug                     = Column(String(100), unique=True, nullable=False, index=True)
    admin_user_id            = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"),
        unique=True, nullable=True
    )

    # Operating centre — immutable for tenant admin
    center_latitude          = Column(Numeric(10, 7), nullable=False)
    center_longitude         = Column(Numeric(10, 7), nullable=False)
    center_address           = Column(Text, nullable=False)

    # Commercial terms (set by super admin)
    one_time_fee             = Column(Numeric(12, 2), nullable=False, default=0)
    platform_charge_percent  = Column(Numeric(5, 2), nullable=False, default=0)

    # Settlement bank details (managed by super admin)
    bank_account_holder_name = Column(String(150), nullable=True)
    bank_account_number      = Column(String(50), nullable=True)
    bank_ifsc_code           = Column(String(20), nullable=True)
    bank_name                = Column(String(150), nullable=True)

    is_active                = Column(Boolean, default=True)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), onupdate=func.now())

    admin_user  = relationship("User", foreign_keys=[admin_user_id])
    users       = relationship(
        "User", back_populates="tenant", foreign_keys="User.tenant_id"
    )
    restaurants = relationship("Restaurant", back_populates="tenant")
    zones       = relationship(
        "DeliveryZone", back_populates="tenant",
        cascade="all, delete-orphan", order_by="DeliveryZone.radius_km"
    )


class DeliveryZone(Base):
    """
    Delivery pricing rings around the tenant centre.
    Admin manages zones; cannot change centre coordinates.
    pricing_type: 'flat' = fixed Rs for the zone | 'per_km' = rate × distance
    """
    __tablename__ = "delivery_zones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_zone_tenant_name"),
    )

    id            = Column(Integer, primary_key=True, index=True)
    tenant_id     = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name          = Column(String(100), nullable=False)       # e.g. Zone 1
    radius_km     = Column(Numeric(8, 2), nullable=False)     # e.g. 2.00
    pricing_type  = Column(String(20), nullable=False)        # flat | per_km
    rate          = Column(Numeric(10, 2), nullable=False)    # Rs flat or Rs/km
    sort_order    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="zones")
