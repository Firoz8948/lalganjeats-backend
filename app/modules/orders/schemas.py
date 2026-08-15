# backend/app/modules/orders/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List


class PlaceOrderItem(BaseModel):
    menu_item_id: int
    quantity: int = Field(..., ge=1, le=50)
    variant_id: Optional[int] = None


class PlaceOrderRequest(BaseModel):
    restaurant_id: int
    address_id: Optional[int] = None
    delivery_address: Optional[str] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    payment_method: str = "cash"  # cash | online
    notes: Optional[str] = None
    promo_code: Optional[str] = None
    items: List[PlaceOrderItem]


class PlaceOrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    payment_method: str
    payment_status: str
    total_amount: float
    delivery_fee: float
    discount: float
    distance_km: Optional[float] = None
    eta_minutes: Optional[int] = None
    online_payment_stub: Optional[dict] = None
