# backend/app/modules/getlocation/schemas.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LocationUpdateRequest(BaseModel):
    """
    Device GPS ping from the delivery partner app.

    Sent once on Accept and then every RIDER_LOCATION_INTERVAL_SECONDS
    (default 2 min) while an order is picked up. Stored in our DB only —
    never forwarded to Google.
    """
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    order_id: Optional[int] = None
    accuracy_m: Optional[float] = None
    source: Optional[str] = Field(None, max_length=20)  # accept | pickup_ping | ping

    @field_validator("latitude", "longitude")
    @classmethod
    def finite(cls, v: float) -> float:
        if v != v:  # NaN
            raise ValueError("Invalid coordinate")
        return v


class LocationOut(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    updated_at: Optional[datetime] = None
    delivery_partner_id: Optional[int] = None
    order_id: Optional[int] = None
    order_status: Optional[str] = None
    available: bool = False
    message: Optional[str] = None
