from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


TargetType = Literal["restaurant", "delivery_partner"]
PeriodType = Literal["daily", "last_week", "last_month", "overall", "custom"]
DeliveryChannel = Literal["email", "whatsapp"]


class ReportRequest(BaseModel):
    target_type: TargetType
    target_id: int
    period: PeriodType
    custom_start: datetime | None = None
    custom_end: datetime | None = None

    @model_validator(mode="after")
    def validate_custom_range(self):
        if self.period == "custom" and (
            self.custom_start is None or self.custom_end is None
        ):
            raise ValueError("Custom start and end dates are required")
        return self


class ReportSendRequest(ReportRequest):
    channel: DeliveryChannel
    recipient: str | None = Field(default=None, max_length=200)


class ReportRecipient(BaseModel):
    id: int
    target_type: TargetType
    name: str
    phone: str | None = None
    email: str | None = None
    is_active: bool = True


class ReportSummary(BaseModel):
    target_type: TargetType
    target_id: int
    target_name: str
    period: PeriodType
    period_label: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    order_count: int
    delivered_orders: int
    cancelled_orders: int
    gross_order_value: float
    discounts: float
    delivery_fees: float
    platform_charges: float
    gross_earnings: float
    platform_fees: float
    settled_amount: float
    unsettled_amount: float
    settled_orders: int
    unsettled_orders: int


class ReportSendResponse(BaseModel):
    ok: bool
    channel: DeliveryChannel
    recipient: str
    delivery_id: int
    message: str
