from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional


class RestaurantPublicResponse(BaseModel):
    id: int
    name: str
    cuisine: str = ""
    rating: float = 4.0
    review_count: int = 0
    delivery_time: str = "30-40 min"
    delivery_fee: str = "Free delivery"
    min_order: str = "₹100"
    is_open: bool = True
    offer_text: str | None = None
    image_emoji: str = "🍛"
    image_bg: str = "#FFF3EF"
    logo_url: str | None = None
    list_banner_url: str | None = None
    banner_url: str | None = None
    address: str | None = None
    city: str = "Lalganj"
    latitude: float | None = None
    longitude: float | None = None


class RestaurantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str = "Lalganj"
    pincode: str | None = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    logo_url: str | None = None
    list_banner_url: str | None = None
    banner_url: str | None = None
    owner_phone: str = Field(..., min_length=10, max_length=15)
    owner_name: str | None = None
    is_approved: bool = True


class RestaurantUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    logo_url: Optional[str] = None
    list_banner_url: Optional[str] = None
    banner_url: Optional[str] = None
    is_open: Optional[bool] = None
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
    owner_name: Optional[str] = None
