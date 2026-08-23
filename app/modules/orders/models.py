# backend/app/modules/orders/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean,
    Text, DateTime, DECIMAL, ForeignKey, Numeric, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id                  = Column(Integer, primary_key=True, index=True)
    order_number        = Column(String(20), unique=True, nullable=False)
    tenant_id           = Column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    customer_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    restaurant_id       = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    delivery_partner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status              = Column(String(30), default="pending")
    # pending → confirmed → preparing → ready_for_pickup → assigned
    # → picked_up → on_the_way → delivered | cancelled
    payment_method      = Column(String(20), default="cash")  # cash | online | upi | split
    payment_status      = Column(String(20), default="pending")
    subtotal            = Column(DECIMAL(10, 2), nullable=False)
    delivery_fee        = Column(DECIMAL(10, 2), default=0)
    discount            = Column(DECIMAL(10, 2), default=0)
    total_amount        = Column(DECIMAL(10, 2), nullable=False)
    display_total       = Column(DECIMAL(10, 2), nullable=True)
    actual_total        = Column(DECIMAL(10, 2), nullable=True)
    platform_fee        = Column(DECIMAL(10, 2), nullable=True)
    admin_earning       = Column(DECIMAL(10, 2), nullable=True)
    delivery_partner_earning = Column(DECIMAL(10, 2), nullable=True)
    razorpay_order_id   = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    delivery_address    = Column(Text)
    delivery_latitude   = Column(Numeric(10, 7), nullable=True)
    delivery_longitude  = Column(Numeric(10, 7), nullable=True)
    distance_km         = Column(Numeric(8, 2), nullable=True)
    eta_minutes         = Column(Integer, nullable=True)
    notes               = Column(Text)
    delivery_otp        = Column(String(6), nullable=True)
    delivery_otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    delivery_otp_verified_at = Column(DateTime(timezone=True), nullable=True)
    # Doorstep collection (COD / split). Prepaid orders keep these null.
    cash_collected      = Column(DECIMAL(10, 2), nullable=True)
    online_collected    = Column(DECIMAL(10, 2), nullable=True)
    promo_code_id       = Column(
        Integer,
        ForeignKey(
            "promo_codes.id", ondelete="SET NULL",
            use_alter=True, name="fk_orders_promo_code_id",
        ),
        nullable=True, index=True,
    )
    promo_code          = Column(String(40), nullable=True)
    promo_percent_off   = Column(DECIMAL(5, 2), nullable=True)
    promo_free_delivery = Column(Boolean, default=False)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

    customer         = relationship("User", foreign_keys=[customer_id],
                                    back_populates="orders_as_customer")
    delivery_partner = relationship("User", foreign_keys=[delivery_partner_id],
                                    back_populates="orders_as_delivery")
    restaurant       = relationship("Restaurant", back_populates="orders")
    items            = relationship("OrderItem", back_populates="order",
                                    cascade="all, delete-orphan")
    restaurant_earning = relationship(
        "RestaurantEarning", back_populates="order", uselist=False
    )
    delivery_earning = relationship(
        "DeliveryEarning", back_populates="order", uselist=False
    )
    promo_usage = relationship(
        "PromoCodeUsage", back_populates="order", uselist=False
    )
    delivery_offers = relationship(
        "DeliveryOffer", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id           = Column(Integer, primary_key=True)
    order_id     = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    variant_id   = Column(
        Integer,
        ForeignKey("menu_item_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name         = Column(String(150), nullable=False)
    variant_label = Column(String(40), nullable=True)
    price        = Column(DECIMAL(10, 2), nullable=False)
    display_price = Column(DECIMAL(10, 2), nullable=True)
    actual_price  = Column(DECIMAL(10, 2), nullable=True)
    quantity     = Column(Integer, nullable=False, default=1)
    subtotal     = Column(DECIMAL(10, 2), nullable=False)

    order        = relationship("Order", back_populates="items")
    menu_item    = relationship("MenuItem", back_populates="order_items")
    variant      = relationship("MenuItemVariant", back_populates="order_items")


class DeliveryProfile(Base):
    __tablename__ = "delivery_profiles"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"),
                            unique=True, nullable=False)
    vehicle_type   = Column(String(50))
    vehicle_number = Column(String(20))
    is_online      = Column(Boolean, default=False)
    total_earnings = Column(DECIMAL(10, 2), default=0)
    current_latitude  = Column(Numeric(10, 7), nullable=True)
    current_longitude = Column(Numeric(10, 7), nullable=True)
    location_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    user           = relationship("User", back_populates="delivery_profile")


class DeliveryOffer(Base):
    """Cascade offer ring: nearest first, expand every N seconds or on reject."""
    __tablename__ = "delivery_offers"
    __table_args__ = (
        UniqueConstraint("order_id", "delivery_partner_id", name="uq_offer_order_partner"),
    )

    id                   = Column(Integer, primary_key=True)
    order_id             = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    delivery_partner_id  = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rank                 = Column(Integer, nullable=False)  # 1 = nearest
    distance_km          = Column(Numeric(8, 2), nullable=True)
    status               = Column(String(20), default="offered")
    # offered | accepted | rejected | expired | superseded
    offered_at           = Column(DateTime(timezone=True), server_default=func.now())
    expires_at           = Column(DateTime(timezone=True), nullable=True)
    responded_at         = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="delivery_offers")
    partner = relationship("User", foreign_keys=[delivery_partner_id])
