from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.modules.restaurants.models import Restaurant
from app.modules.restaurants.schemas import RestaurantPublicResponse, RestaurantCreateRequest
from app.modules.users.models import User

EMOJI_PALETTE = ["🍛", "🥘", "🍔", "🍮", "🥞", "🍗", "☕", "🥗"]
BG_PALETTE = ["#FFF3EF", "#FFF9EF", "#F0FFF4", "#FFF0F5", "#F0F4FF", "#FFF8EF", "#F5F0FF", "#EFFFF5"]


def _to_public(restaurant: Restaurant, index: int = 0) -> dict:
    lat = getattr(restaurant, "latitude", None)
    lng = getattr(restaurant, "longitude", None)
    return RestaurantPublicResponse(
        id=restaurant.id,
        name=restaurant.name,
        cuisine=restaurant.description or "",
        is_open=restaurant.is_open,
        logo_url=restaurant.logo_url,
        list_banner_url=getattr(restaurant, "list_banner_url", None),
        banner_url=getattr(restaurant, "banner_url", None),
        address=restaurant.address,
        city=restaurant.city or "Lalganj",
        latitude=float(lat) if lat is not None else None,
        longitude=float(lng) if lng is not None else None,
        image_emoji=EMOJI_PALETTE[index % len(EMOJI_PALETTE)],
        image_bg=BG_PALETTE[index % len(BG_PALETTE)],
    ).model_dump()


def list_public_restaurants(db: Session) -> list[dict]:
    restaurants = (
        db.query(Restaurant)
        .filter(
            Restaurant.is_active == True,
            Restaurant.is_approved == True,
        )
        .order_by(Restaurant.created_at.desc())
        .all()
    )
    return [_to_public(r, i) for i, r in enumerate(restaurants)]


def get_public_restaurant(db: Session, restaurant_id: int) -> dict:
    restaurant = (
        db.query(Restaurant)
        .filter(
            Restaurant.id == restaurant_id,
            Restaurant.is_active == True,
            Restaurant.is_approved == True,
        )
        .first()
    )
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return _to_public(restaurant, restaurant_id)


def _get_or_create_owner(
    db: Session, phone: str, full_name: str | None, tenant_id: int | None = None
) -> User:
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        if user.role != "restaurant_owner":
            raise HTTPException(
                status_code=400,
                detail=f"Phone already registered as {user.role}",
            )
        if full_name and not user.full_name:
            user.full_name = full_name
        if tenant_id and not user.tenant_id:
            user.tenant_id = tenant_id
        return user

    user = User(
        phone=phone,
        full_name=full_name or "Restaurant Owner",
        role="restaurant_owner",
        tenant_id=tenant_id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def create_restaurant(
    db: Session,
    payload: RestaurantCreateRequest,
    tenant_id: int | None = None,
) -> dict:
    owner = _get_or_create_owner(db, payload.owner_phone, payload.owner_name, tenant_id)

    restaurant = Restaurant(
        owner_id=owner.id,
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        phone=payload.phone,
        address=payload.address,
        city=payload.city,
        pincode=payload.pincode,
        latitude=payload.latitude,
        longitude=payload.longitude,
        logo_url=payload.logo_url,
        list_banner_url=payload.list_banner_url,
        banner_url=payload.banner_url,
        is_open=True,
        is_approved=payload.is_approved,
        is_active=True,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return _to_public(restaurant, 0)


def _admin_row(r: Restaurant) -> dict:
    lat = getattr(r, "latitude", None)
    lng = getattr(r, "longitude", None)
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "owner": r.owner.full_name if r.owner else None,
        "owner_phone": r.owner.phone if r.owner else None,
        "phone": r.phone,
        "address": r.address,
        "city": r.city,
        "pincode": r.pincode,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lng) if lng is not None else None,
        "logo_url": r.logo_url,
        "list_banner_url": getattr(r, "list_banner_url", None),
        "banner_url": getattr(r, "banner_url", None),
        "is_open": r.is_open,
        "is_approved": r.is_approved,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def get_admin_restaurant(
    db: Session, restaurant_id: int, tenant_id: int | None
) -> dict:
    q = db.query(Restaurant).filter(Restaurant.id == restaurant_id)
    if tenant_id is not None:
        q = q.filter(Restaurant.tenant_id == tenant_id)
    restaurant = q.first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return _admin_row(restaurant)


def update_restaurant(
    db: Session,
    restaurant_id: int,
    payload,
    tenant_id: int | None = None,
) -> dict:
    from app.modules.restaurants.schemas import RestaurantUpdateRequest

    q = db.query(Restaurant).filter(Restaurant.id == restaurant_id)
    if tenant_id is not None:
        q = q.filter(Restaurant.tenant_id == tenant_id)
    restaurant = q.first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    data = (
        payload.model_dump(exclude_unset=True)
        if isinstance(payload, RestaurantUpdateRequest)
        else dict(payload)
    )
    owner_name = data.pop("owner_name", None)

    for key, value in data.items():
        setattr(restaurant, key, value)

    if owner_name is not None and restaurant.owner:
        restaurant.owner.full_name = owner_name

    db.commit()
    db.refresh(restaurant)
    return _admin_row(restaurant)
