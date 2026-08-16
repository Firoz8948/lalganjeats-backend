# backend/app/modules/users/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    Text, DateTime, Date, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    full_name     = Column(String(100))
    phone         = Column(String(15), unique=True, index=True)
    email         = Column(String(150), unique=True, index=True, nullable=True)
    password_hash = Column(Text, nullable=True)
    role          = Column(String(20), nullable=False)
    # Set for tenant-scoped roles (admin, restaurant_owner, delivery_partner)
    # use_alter breaks circular FK with tenants.admin_user_id
    tenant_id     = Column(
        Integer,
        ForeignKey(
            "tenants.id", ondelete="SET NULL",
            use_alter=True, name="fk_users_tenant_id",
        ),
        nullable=True, index=True,
    )
    is_active     = Column(Boolean, default=True)
    is_verified   = Column(Boolean, default=False)
    profile_image = Column(Text, nullable=True)
    legal_terms_version = Column(String(20), nullable=True)
    legal_terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship(
        "Tenant", back_populates="users", foreign_keys=[tenant_id]
    )
    customer_profile = relationship(
        "CustomerProfile", back_populates="user",
        uselist=False, cascade="all, delete-orphan"
    )
    addresses        = relationship(
        "Address", back_populates="user",
        cascade="all, delete-orphan"
    )
    restaurants      = relationship(
        "Restaurant", back_populates="owner",
        foreign_keys="Restaurant.owner_id"
    )
    delivery_profile = relationship(
        "DeliveryProfile", back_populates="user",
        uselist=False
    )
    delivery_partner_details = relationship(
        "DeliveryPartnerDetails",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    orders_as_customer  = relationship(
        "Order", back_populates="customer",
        foreign_keys="Order.customer_id"
    )
    orders_as_delivery  = relationship(
        "Order", back_populates="delivery_partner",
        foreign_keys="Order.delivery_partner_id"
    )
    customer_settings = relationship(
        "CustomerSettings", back_populates="user",
        uselist=False, cascade="all, delete-orphan"
    )
    bank_accounts = relationship(
        "BankAccount", back_populates="user", cascade="all, delete-orphan"
    )
    withdrawals = relationship(
        "Withdrawal", back_populates="user", cascade="all, delete-orphan"
    )


class CustomerProfile(Base):
    """
    Extended profile for customers only.
    Linked 1-to-1 with users table.
    """
    __tablename__ = "customer_profiles"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    full_name   = Column(String(100))
    email       = Column(String(150), nullable=True)
    phone       = Column(String(15))
    date_of_birth = Column(Date, nullable=True)
    gender      = Column(String(10), nullable=True)  # male|female|other
    profile_image = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="customer_profile")


class Address(Base):
    """
    Customer delivery addresses.
    One customer can have many addresses.
    Only one can be default.
    """
    __tablename__ = "addresses"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    label        = Column(String(50), default="Home")   # Home|Work|Other
    full_address = Column(Text, nullable=False)
    landmark     = Column(String(200), nullable=True)
    city         = Column(String(100), default="Lalganj")
    pincode      = Column(String(10), nullable=True)
    latitude     = Column(String(20), nullable=True)
    longitude    = Column(String(20), nullable=True)
    is_default   = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="addresses")


class CustomerSettings(Base):
    """
    App settings per customer.
    Created with defaults on first save.
    """
    __tablename__ = "customer_settings"

    id                    = Column(Integer, primary_key=True)
    user_id               = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    # Notifications
    notif_order_updates   = Column(Boolean, default=True)
    notif_offers          = Column(Boolean, default=True)
    notif_sms             = Column(Boolean, default=True)

    # Preferences
    preferred_language    = Column(String(10), default="en")
    preferred_payment     = Column(String(20), default="cash")  # cash|upi

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="customer_settings")
