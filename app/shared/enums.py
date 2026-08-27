from enum import Enum

class UserRole(str, Enum):
    CUSTOMER         = "customer"
    DELIVERY_PARTNER = "delivery_partner"
    HOTEL_PARTNER    = "hotel_partner"
    ADMIN            = "admin"

class OrderStatus(str, Enum):
    PENDING    = "pending"
    ACCEPTED   = "accepted"
    READY      = "ready"
    PICKED_UP  = "picked_up"
    DELIVERED  = "delivered"
    CANCELLED  = "cancelled"

class PaymentMethod(str, Enum):
    UPI    = "upi"
    CASH   = "cash"
    ONLINE = "online"
    SPLIT  = "split"

class PaymentStatus(str, Enum):
    PENDING  = "pending"
    SUCCESS  = "success"
    FAILED   = "failed"
    REFUNDED = "refunded"
