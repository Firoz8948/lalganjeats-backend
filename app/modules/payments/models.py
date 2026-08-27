# backend/app/modules/payments/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class PaymentSettings(Base):
    __tablename__ = "payment_settings"

    id = Column(Integer, primary_key=True, default=1)
    delivery_charge = Column(Float, default=30.0)
    free_delivery_above = Column(Float, default=299.0)
    delivery_boy_per_order_earning = Column(Float, default=25.0)
    platform_fee_percent = Column(Float, default=5.0)
    # Fixed rupee fee added to what the customer pays at checkout.
    platform_charge_rupees = Column(Float, default=2.0)
    display_price_markup_percent = Column(Float, default=30.0)
    allow_prepaid_orders = Column(Boolean, default=True, nullable=False)
    allow_cod_orders = Column(Boolean, default=True, nullable=False)
    cod_max_order_amount = Column(Float, default=500.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RestaurantEarning(Base):
    __tablename__ = "restaurant_earnings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    display_price_total = Column(Float, nullable=False)
    actual_price_total = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    amount_earned = Column(Float, nullable=False)
    transfer_status = Column(String(20), default="pending")
    razorpay_transfer_id = Column(String, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    settled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="earnings")
    order = relationship("Order", back_populates="restaurant_earning")


class DeliveryEarning(Base):
    __tablename__ = "delivery_earnings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_partner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    amount_earned = Column(Float, nullable=False)
    transfer_status = Column(String(20), default="pending")
    razorpay_transfer_id = Column(String, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    settled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    delivery_partner = relationship("User", foreign_keys=[delivery_partner_id])
    order = relationship("Order", back_populates="delivery_earning")


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending")
    razorpay_payout_id = Column(String, nullable=True)
    bank_account_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="withdrawals")


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)
    account_holder_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    ifsc_code = Column(String, nullable=False)
    razorpay_linked_account_id = Column(String, nullable=True)
    razorpay_fund_account_id = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    is_primary = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="bank_accounts")


class CashRemittance(Base):
    """Delivery partner remits doorstep cash to the platform via PayU."""

    __tablename__ = "cash_remittances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_partner_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)
    payu_txnid = Column(String(100), nullable=True, index=True)
    payu_mihpayid = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

    delivery_partner = relationship("User", foreign_keys=[delivery_partner_id])
    orders = relationship("Order", back_populates="cash_remittance")
