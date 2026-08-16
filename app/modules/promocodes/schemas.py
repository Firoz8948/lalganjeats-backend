# backend/app/modules/promocodes/schemas.py
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


ClientChannel = Literal["web", "android_app", "ios_app"]
PromoChannel = Literal["all", "mobile_app"]


class PromoCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    channel: PromoChannel = "all"
    percent_off: Optional[Decimal] = Field(None, ge=0, le=100)
    free_delivery: bool = False
    expires_at: Optional[datetime] = None
    max_uses: int = Field(..., ge=0)  # 0 = unlimited
    description: Optional[str] = Field(None, max_length=255)
    is_public: bool = False

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def require_benefit(self):
        if not self.free_delivery and (self.percent_off is None or self.percent_off <= 0):
            raise ValueError("Set percent_off and/or free_delivery")
        return self


class PromoUpdateRequest(BaseModel):
    channel: Optional[PromoChannel] = None
    percent_off: Optional[Decimal] = Field(None, ge=0, le=100)
    free_delivery: Optional[bool] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = Field(None, ge=0)  # 0 = unlimited
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None


class PromoOut(BaseModel):
    id: int
    code: str
    channel: str
    percent_off: Optional[Decimal]
    free_delivery: bool
    expires_at: Optional[datetime]
    max_uses: int
    remaining_uses: int
    used_count: int = 0
    is_active: bool
    is_public: bool = False
    is_expired: bool = False
    description: Optional[str]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PublicPromoOut(BaseModel):
    code: str
    channel: str
    percent_off: Optional[Decimal]
    free_delivery: bool
    description: Optional[str]
    expires_at: Optional[datetime] = None


class PromoValidateRequest(BaseModel):
    code: str
    client_channel: ClientChannel = "web"
    subtotal: Optional[Decimal] = Field(None, ge=0)
    delivery_fee: Optional[Decimal] = Field(None, ge=0)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


class PromoValidateResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    message: str
    download_required: bool = False
    code: Optional[str] = None
    channel: Optional[str] = None
    percent_off: Optional[Decimal] = None
    free_delivery: bool = False
    discount_amount: Optional[Decimal] = None
    delivery_fee_after: Optional[Decimal] = None
    remaining_uses: Optional[int] = None


class PromoUsageItemOut(BaseModel):
    name: str
    quantity: int
    price: Decimal
    subtotal: Decimal


class PromoUsageOut(BaseModel):
    id: int
    order_id: int
    order_number: str
    customer_name: Optional[str]
    customer_phone: Optional[str]
    restaurant_name: Optional[str]
    discount_amount: Decimal
    percent_off_snapshot: Optional[Decimal]
    free_delivery_applied: bool
    client_channel: str
    created_at: Optional[datetime]
    items: list[PromoUsageItemOut] = []
