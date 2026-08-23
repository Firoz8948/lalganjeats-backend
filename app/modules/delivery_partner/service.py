import re
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.modules.auth.credentials import apply_partner_credentials
from app.modules.delivery_partner.models import DeliveryPartnerDetails
from app.modules.delivery_partner.schemas import (
    DeliveryPartnerCreate,
    DeliveryPartnerCredentialsUpdate,
)
from app.modules.orders.models import DeliveryProfile
from app.modules.payments.models import BankAccount
from app.modules.users.models import User


DOCUMENT_FIELD_MAP = {
    "rc": "rc_document_key",
    "aadhaar": "aadhaar_document_key",
    "pan": "pan_document_key",
    "bank_passbook": "bank_passbook_document_key",
}


def calculate_age(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    if dob > today:
        raise ValueError("Date of birth cannot be in the future")
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def normalize_vehicle_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.strip().upper())


def serialize_public_identity(partner: User | None) -> dict | None:
    if partner is None:
        return None
    details = getattr(partner, "delivery_partner_details", None)
    return {
        "name": partner.full_name or "Delivery partner",
        "selfie_url": getattr(details, "selfie_url", None),
        "registered_vehicle_number": getattr(
            details,
            "registered_vehicle_number",
            None,
        ),
        "bike_info": getattr(details, "bike_info", None),
    }


def _partner_query(db: Session, tenant_id: int):
    return (
        db.query(User)
        .options(
            joinedload(User.delivery_partner_details).joinedload(
                DeliveryPartnerDetails.bank_account
            )
        )
        .filter(
            User.role == "delivery_partner",
            User.tenant_id == tenant_id,
        )
    )


def _serialize_admin(partner: User) -> dict:
    details = partner.delivery_partner_details
    if details is None:
        profile = partner.delivery_profile
        return {
            "id": partner.id,
            "full_name": partner.full_name,
            "phone": partner.phone,
            "email": partner.email,
            "username": getattr(partner, "username", None),
            "has_password": bool(getattr(partner, "password_hash", None)),
            "is_active": bool(partner.is_active),
            "profile_complete": False,
            "date_of_birth": None,
            "age": None,
            "address": None,
            "emergency_contact_name": None,
            "emergency_contact_phone": None,
            "joining_date": None,
            "registered_vehicle_number": getattr(profile, "vehicle_number", None),
            "bike_info": getattr(profile, "vehicle_type", None),
            "selfie_url": None,
            "account_holder_name": None,
            "account_number": None,
            "ifsc_code": None,
            "bank_name": None,
            "documents": {purpose: False for purpose in DOCUMENT_FIELD_MAP},
            "created_at": partner.created_at,
        }
    bank = details.bank_account
    return {
        "id": partner.id,
        "full_name": partner.full_name,
        "phone": partner.phone,
        "email": partner.email,
        "username": getattr(partner, "username", None),
        "has_password": bool(getattr(partner, "password_hash", None)),
        "is_active": bool(partner.is_active),
        "profile_complete": True,
        "date_of_birth": details.date_of_birth,
        "age": calculate_age(details.date_of_birth),
        "address": details.address,
        "emergency_contact_name": details.emergency_contact_name,
        "emergency_contact_phone": details.emergency_contact_phone,
        "joining_date": details.joining_date,
        "registered_vehicle_number": details.registered_vehicle_number,
        "bike_info": details.bike_info,
        "selfie_url": details.selfie_url,
        "account_holder_name": bank.account_holder_name if bank else None,
        "account_number": bank.account_number if bank else None,
        "ifsc_code": bank.ifsc_code if bank else None,
        "bank_name": details.bank_name,
        "documents": {
            purpose: bool(getattr(details, field))
            for purpose, field in DOCUMENT_FIELD_MAP.items()
        },
        "created_at": details.created_at,
    }


def list_delivery_partners(db: Session, tenant_id: int) -> list[dict]:
    return [
        _serialize_admin(partner)
        for partner in _partner_query(db, tenant_id)
        .order_by(User.created_at.desc())
        .all()
    ]


def create_delivery_partner(
    db: Session,
    tenant_id: int,
    payload: DeliveryPartnerCreate,
) -> dict:
    if not tenant_id:
        raise HTTPException(400, "Admin is not linked to a tenant")
    existing_user = db.query(User).filter(User.phone == payload.phone).first()
    if existing_user:
        if (
            existing_user.role != "delivery_partner"
            or existing_user.tenant_id != tenant_id
        ):
            raise HTTPException(400, "This phone number is already registered")
        if existing_user.delivery_partner_details:
            raise HTTPException(400, "This delivery partner is already onboarded")

    vehicle_number = normalize_vehicle_number(payload.registered_vehicle_number)
    if not vehicle_number:
        raise HTTPException(400, "Registered vehicle number is required")
    if (
        db.query(DeliveryPartnerDetails)
        .filter(
            DeliveryPartnerDetails.registered_vehicle_number == vehicle_number
        )
        .first()
    ):
        raise HTTPException(400, "This vehicle number is already registered")

    if existing_user:
        user = existing_user
        user.full_name = payload.full_name.strip()
        user.email = payload.email
        user.is_active = True
        user.is_verified = True
    else:
        user = User(
            full_name=payload.full_name.strip(),
            phone=payload.phone,
            email=payload.email,
            role="delivery_partner",
            tenant_id=tenant_id,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()

    apply_partner_credentials(
        db,
        user,
        username=payload.username,
        password=payload.password,
    )

    bank = (
        db.query(BankAccount)
        .filter(
            BankAccount.user_id == user.id,
            BankAccount.role == "delivery_partner",
            BankAccount.is_primary == True,
        )
        .first()
    )
    if bank:
        bank.account_holder_name = payload.account_holder_name.strip()
        bank.account_number = payload.account_number.strip()
        bank.ifsc_code = payload.ifsc_code
    else:
        bank = BankAccount(
            user_id=user.id,
            role="delivery_partner",
            account_holder_name=payload.account_holder_name.strip(),
            account_number=payload.account_number.strip(),
            ifsc_code=payload.ifsc_code,
            is_verified=False,
            is_primary=True,
        )
        db.add(bank)
        db.flush()

    details = DeliveryPartnerDetails(
        user_id=user.id,
        bank_account_id=bank.id,
        date_of_birth=payload.date_of_birth,
        address=payload.address.strip(),
        emergency_contact_name=(
            payload.emergency_contact_name.strip()
            if payload.emergency_contact_name
            else None
        ),
        emergency_contact_phone=payload.emergency_contact_phone,
        joining_date=payload.joining_date,
        registered_vehicle_number=vehicle_number,
        bike_info=payload.bike_info.strip(),
        selfie_url=payload.selfie_url,
        rc_document_key=payload.rc_document_key,
        aadhaar_document_key=payload.aadhaar_document_key,
        pan_document_key=payload.pan_document_key,
        bank_passbook_document_key=payload.bank_passbook_document_key,
        bank_name=payload.bank_name.strip() if payload.bank_name else None,
    )
    db.add(details)
    delivery_profile = user.delivery_profile
    if delivery_profile:
        delivery_profile.vehicle_type = "bike"
        delivery_profile.vehicle_number = vehicle_number
        delivery_profile.is_online = False
    else:
        db.add(DeliveryProfile(
            user_id=user.id,
            vehicle_type="bike",
            vehicle_number=vehicle_number,
            is_online=False,
        ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(400, "Could not create delivery partner")

    partner = _partner_query(db, tenant_id).filter(User.id == user.id).first()
    return _serialize_admin(partner)


def set_delivery_partner_status(
    db: Session,
    tenant_id: int,
    partner_id: int,
    is_active: bool,
) -> dict:
    partner = (
        _partner_query(db, tenant_id)
        .filter(User.id == partner_id)
        .first()
    )
    if not partner:
        raise HTTPException(404, "Delivery partner not found")
    partner.is_active = is_active
    if not is_active and partner.delivery_profile:
        partner.delivery_profile.is_online = False
    db.commit()
    return {"id": partner.id, "is_active": bool(partner.is_active)}


def update_delivery_partner_credentials(
    db: Session,
    tenant_id: int,
    partner_id: int,
    payload: DeliveryPartnerCredentialsUpdate,
) -> dict:
    partner = (
        _partner_query(db, tenant_id)
        .filter(User.id == partner_id)
        .first()
    )
    if not partner:
        raise HTTPException(404, "Delivery partner not found")
    if payload.username is None and not (payload.password and str(payload.password).strip()):
        raise HTTPException(400, "Provide a username and/or password")
    apply_partner_credentials(
        db,
        partner,
        username=payload.username,
        password=payload.password,
    )
    db.commit()
    db.refresh(partner)
    return _serialize_admin(partner)


def get_document_key(
    db: Session,
    tenant_id: int,
    partner_id: int,
    purpose: str,
) -> str:
    field = DOCUMENT_FIELD_MAP.get(purpose)
    if field is None:
        raise HTTPException(404, "Unknown document type")
    partner = (
        _partner_query(db, tenant_id)
        .filter(User.id == partner_id)
        .first()
    )
    if not partner or not partner.delivery_partner_details:
        raise HTTPException(404, "Delivery partner not found")
    key = getattr(partner.delivery_partner_details, field)
    if not key:
        raise HTTPException(404, "Document not uploaded")
    return key
