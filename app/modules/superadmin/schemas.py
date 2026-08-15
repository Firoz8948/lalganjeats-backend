# backend/app/modules/superadmin/schemas.py
from decimal import Decimal
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


PricingType = Literal["flat", "per_km"]


# ── Tenant (created by super admin) ──────────────────────────────────────────

class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    slug: Optional[str] = Field(None, max_length=100)

    # Admin credentials for this tenant
    admin_email: str = Field(..., min_length=3, max_length=150)
    admin_password: str = Field(..., min_length=4, max_length=100)
    admin_full_name: str = Field("Tenant Admin", max_length=100)

    # Centre — locked for tenant admin (super admin can still edit later)
    center_latitude: Decimal
    center_longitude: Decimal
    center_address: str = Field(..., min_length=5)

    # Commercial
    one_time_fee: Decimal = Field(Decimal("0"), ge=0)
    platform_charge_percent: Decimal = Field(Decimal("0"), ge=0, le=100)

    # Bank / settlement
    bank_account_holder_name: Optional[str] = Field(None, max_length=150)
    bank_account_number: Optional[str] = Field(None, max_length=50)
    bank_ifsc_code: Optional[str] = Field(None, max_length=20)
    bank_name: Optional[str] = Field(None, max_length=150)

    @field_validator("admin_email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip().lower().replace(" ", "-")

    @field_validator("bank_ifsc_code")
    @classmethod
    def normalize_ifsc(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v


class TenantUpdateRequest(BaseModel):
    """Super admin can edit centre, commercial terms, admin profile, bank details."""
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    center_latitude: Optional[Decimal] = None
    center_longitude: Optional[Decimal] = None
    center_address: Optional[str] = Field(None, min_length=5)
    one_time_fee: Optional[Decimal] = Field(None, ge=0)
    platform_charge_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None

    admin_email: Optional[str] = Field(None, min_length=3, max_length=150)
    admin_full_name: Optional[str] = Field(None, max_length=100)
    admin_password: Optional[str] = Field(None, min_length=4, max_length=100)

    bank_account_holder_name: Optional[str] = Field(None, max_length=150)
    bank_account_number: Optional[str] = Field(None, max_length=50)
    bank_ifsc_code: Optional[str] = Field(None, max_length=20)
    bank_name: Optional[str] = Field(None, max_length=150)

    @field_validator("admin_email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v

    @field_validator("bank_ifsc_code")
    @classmethod
    def normalize_ifsc(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v


class TenantAdminResetPassword(BaseModel):
    new_password: str = Field(..., min_length=4, max_length=100)


class ZoneOut(BaseModel):
    id: int
    name: str
    radius_km: Decimal
    pricing_type: str
    rate: Decimal
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class TenantOut(BaseModel):
    id: int
    name: str
    slug: str
    admin_user_id: Optional[int]
    admin_email: Optional[str] = None
    admin_full_name: Optional[str] = None
    center_latitude: Decimal
    center_longitude: Decimal
    center_address: str
    one_time_fee: Decimal
    platform_charge_percent: Decimal
    bank_account_holder_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    is_active: bool
    zones: list[ZoneOut] = []
    restaurant_count: int = 0

    model_config = {"from_attributes": True}


class TenantListItem(BaseModel):
    id: int
    name: str
    slug: str
    admin_email: Optional[str] = None
    center_address: str
    center_latitude: Optional[Decimal] = None
    center_longitude: Optional[Decimal] = None
    one_time_fee: Decimal
    platform_charge_percent: Decimal
    bank_account_number: Optional[str] = None
    is_active: bool
    restaurant_count: int = 0
    zone_count: int = 0


class ImpersonateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: Optional[str]
    tenant_id: int
    tenant_name: str
    impersonated_by: int
    redirect_to: str = "/admin/dashboard"


# ── Delivery zones (managed by tenant admin) ─────────────────────────────────

class ZoneCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    radius_km: Decimal = Field(..., gt=0)
    pricing_type: PricingType
    rate: Decimal = Field(..., ge=0)
    sort_order: int = 0


class ZoneUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    radius_km: Optional[Decimal] = Field(None, gt=0)
    pricing_type: Optional[PricingType] = None
    rate: Optional[Decimal] = Field(None, ge=0)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class TenantCentreOut(BaseModel):
    """Read-only centre info for tenant admin UI."""
    id: int
    name: str
    slug: str
    center_latitude: Decimal
    center_longitude: Decimal
    center_address: str
    platform_charge_percent: Decimal
    zones: list[ZoneOut] = []
