# backend/app/modules/tracking/schemas.py
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
from app.modules.delivery_partner.schemas import DeliveryPartnerPublic


class LatLng(BaseModel):
    lat: float
    lng: float


class TrackOrderOut(BaseModel):
    """
    Customer tracking snapshot.

    Rider position is only present once the order is picked up, and it is
    refreshed every `rider_ping_seconds` (2 min) from the rider's device.
    Distance / ETA are free straight-line estimates — no Google call.
    """
    available: bool
    message: Optional[str] = None
    order_id: int
    order_number: Optional[str] = None
    order_status: Optional[str] = None
    status_meta: Optional[str] = None
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
    delivery_partner: Optional[DeliveryPartnerPublic] = None
    # Kept for older app bundles; always None now (tracking map is Leaflet/OSM).
    google_maps_api_key: Optional[str] = None
    # Deep link that opens the rider's last position in the Google Maps app.
    rider_maps_url: Optional[str] = None
    rider_ping_seconds: int = 120
    live_tracking: bool = False


class TrackingPublicConfig(BaseModel):
    # Still served for the address search (Places / Geocoding) in the navbar.
    google_maps_api_key: Optional[str] = None
    maps_enabled: bool = False
    app_name: str = "LalganjEats"
    track_poll_seconds: int = 120
    rider_ping_seconds: int = 120
