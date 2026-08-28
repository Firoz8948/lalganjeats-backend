# backend/app/modules/broadcast_notifications/schemas.py
from pydantic import BaseModel, Field
from typing import Optional


class BroadcastNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    target_audience: str = Field(
        default="all",
        description="all | customers | restaurant_owners | delivery_partners"
    )
    image_url: Optional[str] = None
    deep_link: Optional[str] = None


class BroadcastNotificationResponse(BaseModel):
    success: bool
    target_audience: str
    total_eligible_users: int
    sent_count: int
    message: str
