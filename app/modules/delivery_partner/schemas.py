from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


DOCUMENT_TYPES = ("rc", "aadhaar", "pan", "bank_passbook")
UPLOAD_TYPES = ("selfie", *DOCUMENT_TYPES)


class DeliveryPartnerCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    email: str | None = Field(None, max_length=150)
    date_of_birth: date
    address: str = Field(..., min_length=5)
    emergency_contact_name: str | None = Field(None, max_length=100)
    emergency_contact_phone: str | None = Field(None, max_length=15)
    joining_date: date = Field(default_factory=date.today)

    registered_vehicle_number: str = Field(..., min_length=4, max_length=24)
    bike_info: str = Field(..., min_length=2, max_length=500)
    selfie_url: str = Field(..., min_length=1)

    rc_document_key: str | None = None
    aadhaar_document_key: str | None = None
    pan_document_key: str | None = None
    bank_passbook_document_key: str | None = None

    account_holder_name: str = Field(..., min_length=2, max_length=150)
    account_number: str = Field(..., min_length=5, max_length=50)
    ifsc_code: str = Field(..., min_length=4, max_length=20)
    bank_name: str | None = Field(None, max_length=150)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = "".join(ch for ch in value if ch.isdigit())
        if len(cleaned) < 10:
            raise ValueError("Enter a valid phone number")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None

    @field_validator("ifsc_code")
    @classmethod
    def normalize_ifsc(cls, value: str) -> str:
        return value.strip().upper()


class DeliveryPartnerPublic(BaseModel):
    name: str
    selfie_url: str | None = None
    registered_vehicle_number: str | None = None
    bike_info: str | None = None


class DeliveryPartnerOut(BaseModel):
    id: int
    full_name: str
    phone: str
    email: str | None = None
    is_active: bool
    profile_complete: bool
    date_of_birth: date | None = None
    age: int | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    joining_date: date | None = None
    registered_vehicle_number: str | None = None
    bike_info: str | None = None
    selfie_url: str | None = None
    account_holder_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    bank_name: str | None = None
    documents: dict[str, bool]
    created_at: datetime | None = None


class DeliveryPartnerStatusUpdate(BaseModel):
    is_active: bool


class UploadResult(BaseModel):
    purpose: str
    url: str | None = None
    document_key: str | None = None
