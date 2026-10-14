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
    customer_name: Optional[str] = None
    client_channel: Optional[str] = "web"
    device_id: Optional[str] = Field(None, max_length=64)
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
    platform_charge: float = 0
    packing_charge: float = 0
    distance_km: Optional[float] = None
    eta_minutes: Optional[int] = None
    needs_payment: bool = False


class MultiStoreCartStore(BaseModel):
    restaurant_id: int
    items: List[PlaceOrderItem] = Field(..., min_length=1)


class PlaceMultiStoreOrderRequest(BaseModel):
    """Grocery cart spanning several stores: one payment, one rider."""
    stores: List[MultiStoreCartStore] = Field(..., min_length=2)
    address_id: Optional[int] = None
    delivery_address: Optional[str] = None
    delivery_latitude: Optional[float] = None
    delivery_longitude: Optional[float] = None
    payment_method: str = "cash"  # cash | online
    notes: Optional[str] = None
    promo_code: Optional[str] = None
    customer_name: Optional[str] = None
    client_channel: Optional[str] = "web"
    device_id: Optional[str] = Field(None, max_length=64)


class MultiStoreStoreSummary(BaseModel):
    restaurant_id: int
    restaurant_name: str
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    item_count: int
    subtotal: float
    packing_charge: float = 0


class MultiStoreQuoteResponse(BaseModel):
    subtotal: float
    delivery_fee: float
    platform_charge: float
    packing_charge: float
    discount: float = 0
    total_amount: float
    distance_km: Optional[float] = None
    eta_minutes: Optional[int] = None
    stores: List[MultiStoreStoreSummary]


class PlaceMultiStoreOrderResponse(PlaceOrderResponse):
    is_multi_store: bool = True
    stores: List[MultiStoreStoreSummary]
