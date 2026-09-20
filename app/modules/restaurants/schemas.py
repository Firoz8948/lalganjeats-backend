from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional


class CardSlide(BaseModel):
    image_url: str
    text: Optional[str] = None


def normalize_card_slides(raw) -> list[dict]:
    """Keep at most 5 slides that have a non-empty image_url."""
    if not raw:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("image_url") or "").strip()
        if not url:
            continue
        text = str(item.get("text") or "").strip() or None
        out.append({"image_url": url, "text": text})
    return out


def card_slides_for_public(restaurant) -> list[dict]:
    slides = normalize_card_slides(getattr(restaurant, "card_slides", None))
    if slides:
        return slides
    banner = getattr(restaurant, "list_banner_url", None)
    if banner:
        return [{"image_url": banner, "text": None}]
    return []


class RestaurantPublicResponse(BaseModel):
    id: int
    name: str
    slug: str | None = None
    cuisine: str = ""
    rating: float = 4.0
    review_count: int = 0
    delivery_time: str = "30-40 min"
    delivery_fee: str = "Free delivery"
    delivery_charge: float = 0
    min_order: str = "₹100"
    is_open: bool = True
    opening_time: str | None = None
    closing_time: str | None = None
    opens_at_label: str | None = None
    offer_text: str | None = None
    image_emoji: str = "🍛"
    image_bg: str = "#FFF3EF"
    logo_url: str | None = None
    list_banner_url: str | None = None
    card_slides: list[CardSlide] = Field(default_factory=list)
    banner_url: str | None = None
    banner_mobile_url: str | None = None
    address: str | None = None
    city: str = "Lalganj"
    latitude: float | None = None
    longitude: float | None = None
    business_category_id: int | None = None
    business_category: str | None = None
    show_packing_charge: bool = False
    packing_charge: float = 0


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
    card_slides: list[CardSlide] | None = None
    banner_url: str | None = None
    banner_mobile_url: str | None = None
    owner_phone: str = Field(..., min_length=10, max_length=15)
    owner_name: str | None = None
    owner_username: str | None = Field(None, max_length=80)
    owner_password: str | None = Field(None, min_length=4, max_length=100)
    business_category_id: int | None = None
    is_approved: bool = True
    show_packing_charge: bool = False
    packing_charge: Optional[Decimal] = None
    opening_time: str | None = "10:00"
    closing_time: str | None = "22:00"

    @field_validator("card_slides", mode="before")
    @classmethod
    def _norm_create_slides(cls, value):
        if value is None:
            return None
        return normalize_card_slides(value)


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
    card_slides: Optional[list[CardSlide]] = None
    banner_url: Optional[str] = None
    banner_mobile_url: Optional[str] = None
    is_open: Optional[bool] = None
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
    owner_name: Optional[str] = None
    owner_username: Optional[str] = Field(None, max_length=80)
    owner_password: Optional[str] = Field(None, min_length=4, max_length=100)
    business_category_id: Optional[int] = None
    show_packing_charge: Optional[bool] = None
    packing_charge: Optional[Decimal] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None

    @field_validator("card_slides", mode="before")
    @classmethod
    def _norm_update_slides(cls, value):
        if value is None:
            return None
        return normalize_card_slides(value)
