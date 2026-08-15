# backend/app/modules/users/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date


class ProfileUpdate(BaseModel):
    full_name:     Optional[str]      = None
    email:         Optional[str]      = None
    date_of_birth: Optional[date]     = None
    gender:        Optional[str]      = None


class AddressCreate(BaseModel):
    label:        str  = "Home"
    full_address: str
    landmark:     Optional[str] = None
    city:         str  = "Lalganj"
    pincode:      Optional[str] = None
    latitude:     Optional[str] = None
    longitude:    Optional[str] = None
    is_default:   bool = False


class AddressUpdate(BaseModel):
    label:        Optional[str] = None
    full_address: Optional[str] = None
    landmark:     Optional[str] = None
    city:         Optional[str] = None
    pincode:      Optional[str] = None
    is_default:   Optional[bool] = None


class SettingsUpdate(BaseModel):
    notif_order_updates: Optional[bool] = None
    notif_offers:        Optional[bool] = None
    notif_sms:           Optional[bool] = None
    preferred_language:  Optional[str]  = None
    preferred_payment:   Optional[str]  = None
