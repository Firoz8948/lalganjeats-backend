# backend/app/modules/payments/schemas.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentSettingsBase(BaseModel):
    delivery_charge: float = Field(..., ge=0)
    free_delivery_above: float = Field(..., ge=0)
    delivery_boy_per_order_earning: float = Field(..., ge=0)
    platform_fee_percent: float = Field(..., ge=0, le=100)
    display_price_markup_percent: float = Field(..., ge=0, le=500)


class PaymentSettingsUpdate(PaymentSettingsBase):
    pass


class PaymentSettingsResponse(PaymentSettingsBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BankAccountCreate(BaseModel):
    account_holder_name: str
    account_number: str
    ifsc_code: str


class BankAccountResponse(BaseModel):
    id: int
    account_holder_name: str
    account_number: str
    ifsc_code: str
    is_verified: bool
    is_primary: bool
    razorpay_linked_account_id: Optional[str] = None

    class Config:
        from_attributes = True


class WithdrawalRequest(BaseModel):
    amount: float = Field(..., gt=0)


class WithdrawalResponse(BaseModel):
    id: int
    amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class EarningsSummary(BaseModel):
    total_earned: float
    total_withdrawn: float
    available_balance: float
    unsettled_amount: float
    settled_amount: float


class RazorpayOrderCreate(BaseModel):
    order_id: int


class RazorpayOrderResponse(BaseModel):
    razorpay_order_id: str
    amount: float
    currency: str
    key_id: str


class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    order_id: int


class SplitPreview(BaseModel):
    display_total: float
    actual_price_total: float
    delivery_charge: float
    platform_fee: float
    hotel_earning: float
    delivery_earning: float
    admin_earning: float
    customer_pays: float
