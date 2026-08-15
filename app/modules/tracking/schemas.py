# backend/app/modules/tracking/schemas.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class LatLng(BaseModel):
    lat: float
    lng: float


class TrackOrderOut(BaseModel):
    """Customer live tracking snapshot (poll every few seconds)."""
    available: bool
    message: Optional[str] = None
    order_id: int
    order_number: Optional[str] = None
    order_status: Optional[str] = None
    phase: Optional[Literal["to_restaurant", "to_customer", "delivered"]] = None
    rider: Optional[LatLng] = None
    destination: Optional[LatLng] = None
    restaurant: Optional[LatLng] = None
    customer: Optional[LatLng] = None
    eta_minutes: Optional[int] = None
    distance_km: Optional[float] = None
    eta_label: Optional[str] = None
    updated_at: Optional[datetime] = None
    delivery_partner_id: Optional[int] = None
    google_maps_api_key: Optional[str] = None


class TrackingPublicConfig(BaseModel):
    google_maps_api_key: Optional[str] = None
    maps_enabled: bool = False
    app_name: str = "LalganjEats"
    track_poll_seconds: int = 4
