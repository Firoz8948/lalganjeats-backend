from enum import Enum

class UserRole(str, Enum):
    CUSTOMER         = "customer"
    DELIVERY_PARTNER = "delivery_partner"
    HOTEL_PARTNER    = "hotel_partner"
    ADMIN            = "admin"

class OrderStatus(str, Enum):
    PENDING          = "pending"
    CONFIRMED        = "confirmed"
    PREPARING        = "preparing"
    READY_FOR_PICKUP = "ready_for_pickup"
    PICKED_UP        = "picked_up"
    ON_THE_WAY       = "on_the_way"
    DELIVERED        = "delivered"
    CANCELLED        = "cancelled"

class PaymentMethod(str, Enum):
    UPI  = "upi"
    CASH = "cash"

class PaymentStatus(str, Enum):
    PENDING  = "pending"
    SUCCESS  = "success"
    FAILED   = "failed"
    REFUNDED = "refunded"
