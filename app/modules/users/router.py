# backend/app/modules/users/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_customer
from app.modules.users.models import (
    User, CustomerProfile, Address, CustomerSettings
)
from app.modules.users.schemas import (
    ProfileUpdate, AddressCreate, AddressUpdate, SettingsUpdate
)
from app.modules.orders.models import Order

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


# ═══════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════

@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    profile = db.query(CustomerProfile).filter(
        CustomerProfile.user_id == current_user.id
    ).first()

    return {
        "id":         current_user.id,
        "phone":      current_user.phone,
        "full_name":  profile.full_name  if profile else current_user.full_name,
        "email":      profile.email      if profile else current_user.email,
        "gender":     profile.gender     if profile else None,
        "date_of_birth": str(profile.date_of_birth)
                      if profile and profile.date_of_birth else None,
        "profile_image": profile.profile_image
                      if profile else current_user.profile_image,
        "created_at": current_user.created_at.isoformat()
                      if current_user.created_at else None,
    }


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    # Get or create customer profile
    profile = db.query(CustomerProfile).filter(
        CustomerProfile.user_id == current_user.id
    ).first()

    if not profile:
        profile = CustomerProfile(
            user_id   = current_user.id,
            phone     = current_user.phone,
            full_name = current_user.full_name,
        )
        db.add(profile)

    # Update fields
    if payload.full_name is not None:
        profile.full_name = payload.full_name
        current_user.full_name = payload.full_name  # sync to users table

    if payload.email is not None:
        profile.email = payload.email
        current_user.email = payload.email

    if payload.date_of_birth is not None:
        profile.date_of_birth = payload.date_of_birth

    if payload.gender is not None:
        profile.gender = payload.gender

    db.commit()
    db.refresh(profile)

    return {"message": "Profile updated successfully"}


# ═══════════════════════════════════════════
# ADDRESSES
# ═══════════════════════════════════════════

@router.get("/addresses")
def get_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    addresses = db.query(Address).filter(
        Address.user_id == current_user.id
    ).order_by(Address.is_default.desc(), Address.created_at.desc()).all()

    return [
        {
            "id":           a.id,
            "label":        a.label,
            "full_address": a.full_address,
            "landmark":     a.landmark,
            "city":         a.city,
            "pincode":      a.pincode,
            "is_default":   a.is_default,
        }
        for a in addresses
    ]


@router.post("/addresses")
def add_address(
    payload: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    # If new address is default → unset all others
    if payload.is_default:
        db.query(Address).filter(
            Address.user_id == current_user.id
        ).update({"is_default": False})

    # If this is the first address → make it default automatically
    existing_count = db.query(Address).filter(
        Address.user_id == current_user.id
    ).count()

    is_default = payload.is_default or (existing_count == 0)

    address = Address(
        user_id      = current_user.id,
        label        = payload.label,
        full_address = payload.full_address,
        landmark     = payload.landmark,
        city         = payload.city,
        pincode      = payload.pincode,
        latitude     = payload.latitude,
        longitude    = payload.longitude,
        is_default   = is_default,
    )
    db.add(address)
    db.commit()
    db.refresh(address)

    return {"message": "Address added", "id": address.id}


@router.put("/addresses/{address_id}")
def update_address(
    address_id: int,
    payload: AddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    address = db.query(Address).filter(
        Address.id      == address_id,
        Address.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(404, "Address not found")

    # If setting this as default → unset all others first
    if payload.is_default:
        db.query(Address).filter(
            Address.user_id == current_user.id,
            Address.id      != address_id
        ).update({"is_default": False})

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(address, field, value)

    db.commit()
    return {"message": "Address updated"}


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    address = db.query(Address).filter(
        Address.id      == address_id,
        Address.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(404, "Address not found")

    was_default = address.is_default
    db.delete(address)
    db.commit()

    # If deleted address was default → make the next one default
    if was_default:
        next_address = db.query(Address).filter(
            Address.user_id == current_user.id
        ).first()
        if next_address:
            next_address.is_default = True
            db.commit()

    return {"message": "Address deleted"}


@router.patch("/addresses/{address_id}/set-default")
def set_default_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    # Unset all
    db.query(Address).filter(
        Address.user_id == current_user.id
    ).update({"is_default": False})

    # Set this one
    address = db.query(Address).filter(
        Address.id      == address_id,
        Address.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(404, "Address not found")

    address.is_default = True
    db.commit()
    return {"message": "Default address updated"}


# ═══════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════

@router.get("/orders")
def get_my_orders(
    filter: str = "all",   # all | active | completed | cancelled
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    query = db.query(Order).filter(
        Order.customer_id == current_user.id
    )

    if filter == "active":
        query = query.filter(
            Order.status.in_([
                "pending", "confirmed",
                "preparing", "ready_for_pickup",
                "assigned", "picked_up", "on_the_way"
            ])
        )
    elif filter == "completed":
        query = query.filter(Order.status == "delivered")
    elif filter == "cancelled":
        query = query.filter(Order.status == "cancelled")

    orders = query.order_by(Order.created_at.desc()).all()

    from app.modules.delivery_partner.service import serialize_public_identity

    return [
        {
            "id":             o.id,
            "order_number":   o.order_number,
            "restaurant_id":  o.restaurant_id,
            "restaurant_name": o.restaurant.name
                              if o.restaurant else "Unknown",
            "status":         o.status,
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "subtotal":       float(o.subtotal),
            "delivery_fee":   float(o.delivery_fee or 0),
            "total_amount":   float(o.total_amount),
            "distance_km":    float(o.distance_km) if o.distance_km is not None else None,
            "eta_minutes":    o.eta_minutes,
            "delivery_partner": serialize_public_identity(o.delivery_partner),
            "items": [
                {
                    "name":     i.name,
                    "price":    float(i.price),
                    "quantity": i.quantity,
                    "subtotal": float(i.subtotal),
                }
                for i in o.items
            ],
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# ═══════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════

@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    settings = db.query(CustomerSettings).filter(
        CustomerSettings.user_id == current_user.id
    ).first()

    if not settings:
        # Return defaults if none saved yet
        return {
            "notif_order_updates": True,
            "notif_offers":        True,
            "notif_sms":           True,
            "preferred_language":  "en",
            "preferred_payment":   "cash",
        }

    return {
        "notif_order_updates": settings.notif_order_updates,
        "notif_offers":        settings.notif_offers,
        "notif_sms":           settings.notif_sms,
        "preferred_language":  settings.preferred_language,
        "preferred_payment":   settings.preferred_payment,
    }


@router.put("/settings")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_customer)
):
    settings = db.query(CustomerSettings).filter(
        CustomerSettings.user_id == current_user.id
    ).first()

    if not settings:
        settings = CustomerSettings(user_id=current_user.id)
        db.add(settings)

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(settings, field, value)

    db.commit()
    return {"message": "Settings saved"}
