import re

from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.core.maps import haversine_km
from app.modules.auth.credentials import apply_partner_credentials
from app.modules.restaurants.models import CatalogCategory, MenuItem, Restaurant
from app.modules.restaurants.schemas import RestaurantPublicResponse, RestaurantCreateRequest
from app.modules.restaurants.service_area import (
    delivery_charge_for_distance,
    matching_delivery_exception,
)
from app.modules.superadmin.models import Tenant
from app.modules.users.models import User

EMOJI_PALETTE = ["🍛", "🥘", "🍔", "🍮", "🥞", "🍗", "☕", "🥗"]
BG_PALETTE = ["#FFF3EF", "#FFF9EF", "#F0FFF4", "#FFF0F5", "#F0F4FF", "#FFF8EF", "#F5F0FF", "#EFFFF5"]


def slugify_restaurant_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "restaurant"


def ensure_unique_restaurant_slug(
    db: Session,
    base: str,
    *,
    exclude_id: int | None = None,
) -> str:
    slug = base or "restaurant"
    n = 1
    while True:
        q = db.query(Restaurant.id).filter(Restaurant.slug == slug)
        if exclude_id is not None:
            q = q.filter(Restaurant.id != exclude_id)
        if not q.first():
            return slug
        n += 1
        slug = f"{base}-{n}"


def assign_restaurant_slug(
    db: Session,
    restaurant: Restaurant,
    *,
    name: str | None = None,
    force: bool = False,
) -> None:
    """Set slug from name when missing, or when force=True (name changed)."""
    source = name if name is not None else restaurant.name
    base = slugify_restaurant_name(source)
    if not force and restaurant.slug:
        return
    restaurant.slug = ensure_unique_restaurant_slug(
        db, base, exclude_id=restaurant.id
    )


def _to_public(
    restaurant: Restaurant,
    index: int = 0,
    customer_lat: float | None = None,
    customer_lng: float | None = None,
) -> dict:
    lat = getattr(restaurant, "latitude", None)
    lng = getattr(restaurant, "longitude", None)
    delivery_charge = 0.0
    tenant = getattr(restaurant, "tenant", None)
    if (
        tenant is not None
        and customer_lat is not None
        and customer_lng is not None
        and tenant.center_latitude is not None
        and tenant.center_longitude is not None
    ):
        exception = matching_delivery_exception(
            getattr(tenant, "delivery_exceptions", []) or [],
            customer_lat,
            customer_lng,
        )
        if exception is not None:
            delivery_charge = float(exception.delivery_charge)
        else:
            zone_origin_lat = (
                float(lat)
                if lat is not None
                else float(tenant.center_latitude)
            )
            zone_origin_lng = (
                float(lng)
                if lng is not None
                else float(tenant.center_longitude)
            )
            zone_distance = haversine_km(
                customer_lat,
                customer_lng,
                zone_origin_lat,
                zone_origin_lng,
            )
            delivery_charge = delivery_charge_for_distance(
                tenant.zones or [],
                zone_distance,
            ) or 0.0
    return RestaurantPublicResponse(
        id=restaurant.id,
        name=restaurant.name,
        slug=getattr(restaurant, "slug", None),
        cuisine=restaurant.description or "",
        is_open=restaurant.is_open,
        logo_url=restaurant.logo_url,
        list_banner_url=getattr(restaurant, "list_banner_url", None),
        banner_url=getattr(restaurant, "banner_url", None),
        banner_mobile_url=getattr(restaurant, "banner_mobile_url", None),
        address=restaurant.address,
        city=restaurant.city or "Lalganj",
        latitude=float(lat) if lat is not None else None,
        longitude=float(lng) if lng is not None else None,
        delivery_fee=f"₹{delivery_charge:g} delivery",
        delivery_charge=delivery_charge,
        business_category_id=restaurant.business_category_id,
        business_category=(
            restaurant.business_category.name
            if restaurant.business_category
            else None
        ),
        image_emoji=EMOJI_PALETTE[index % len(EMOJI_PALETTE)],
        image_bg=BG_PALETTE[index % len(BG_PALETTE)],
    ).model_dump()


def _restaurant_visible_for_customer(
    restaurant: Restaurant,
    customer_lat: float | None,
    customer_lng: float | None,
) -> bool:
    """Visibility is based on customer distance matching an active zone range."""
    if customer_lat is None or customer_lng is None:
        return False
    tenant = getattr(restaurant, "tenant", None)
    if tenant is None:
        return False
    if matching_delivery_exception(
        getattr(tenant, "delivery_exceptions", []) or [],
        customer_lat,
        customer_lng,
    ) is not None:
        return True
    if tenant.center_latitude is None or tenant.center_longitude is None:
        return False
    distance = haversine_km(
        float(customer_lat),
        float(customer_lng),
        float(tenant.center_latitude),
        float(tenant.center_longitude),
    )
    return delivery_charge_for_distance(tenant.zones or [], distance) is not None


def list_public_restaurants(
    db: Session,
    customer_lat: float | None = None,
    customer_lng: float | None = None,
    subcategory_id: int | None = None,
) -> list[dict]:
    """
    Public list for home/restaurants pages.

    Requires exact customer lat/lng. Returns only restaurants whose tenant
    locked centre is covered by an active delivery-zone range
    (initial km including, final km excluding).
    Missing/invalid coordinates → empty list (frontend shows expanding state).
    """
    if customer_lat is None or customer_lng is None:
        return []

    query = (
        db.query(Restaurant)
        .options(
            joinedload(Restaurant.tenant).joinedload(Tenant.zones),
            joinedload(Restaurant.tenant).joinedload(Tenant.delivery_exceptions),
        )
        .filter(
            Restaurant.is_active == True,
            Restaurant.is_approved == True,
        )
    )
    if subcategory_id is not None:
        query = (
            query.join(MenuItem, MenuItem.restaurant_id == Restaurant.id)
            .filter(
                MenuItem.business_subcategory_id == subcategory_id,
                MenuItem.is_deleted == False,
                MenuItem.is_available == True,
            )
            .distinct()
        )
    restaurants = query.order_by(Restaurant.created_at.desc()).all()
    visible = [
        r
        for r in restaurants
        if _restaurant_visible_for_customer(r, customer_lat, customer_lng)
    ]
    # Prioritize open restaurants on top, closed restaurants at the bottom
    visible.sort(key=lambda r: (not getattr(r, "is_open", False)))
    return [
        _to_public(r, i, customer_lat, customer_lng)
        for i, r in enumerate(visible)
    ]


def resolve_restaurant_key(db: Session, key: str) -> Restaurant | None:
    """Look up by numeric id or public slug (active + approved)."""
    key = (key or "").strip()
    if not key:
        return None
    q = (
        db.query(Restaurant)
        .options(
            joinedload(Restaurant.tenant).joinedload(Tenant.zones),
            joinedload(Restaurant.tenant).joinedload(Tenant.delivery_exceptions),
            joinedload(Restaurant.business_category),
        )
        .filter(
            Restaurant.is_active == True,  # noqa: E712
            Restaurant.is_approved == True,  # noqa: E712
        )
    )
    if key.isdigit():
        return q.filter(Restaurant.id == int(key)).first()
    return q.filter(Restaurant.slug == key).first()


def get_public_restaurant(
    db: Session,
    restaurant_key: str | int,
    customer_lat: float | None = None,
    customer_lng: float | None = None,
) -> dict:
    restaurant = resolve_restaurant_key(db, str(restaurant_key))
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not _restaurant_visible_for_customer(restaurant, customer_lat, customer_lng):
        raise HTTPException(
            status_code=404,
            detail="Restaurant is outside your delivery area",
        )
    return _to_public(
        restaurant,
        restaurant.id,
        customer_lat,
        customer_lng,
    )


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
    apply_partner_credentials(
        db,
        owner,
        username=payload.owner_username,
        password=payload.owner_password,
    )
    category_id = payload.business_category_id
    if category_id is None:
        default_category = db.query(CatalogCategory).filter(
            CatalogCategory.slug == "restaurant",
            CatalogCategory.is_active == True,
        ).first()
        category_id = default_category.id if default_category else None
    elif not db.query(CatalogCategory).filter(
        CatalogCategory.id == category_id,
        CatalogCategory.is_active == True,
    ).first():
        raise HTTPException(status_code=400, detail="Invalid business category")

    base_slug = slugify_restaurant_name(payload.name)
    unique_slug = ensure_unique_restaurant_slug(db, base_slug)

    restaurant = Restaurant(
        owner_id=owner.id,
        tenant_id=tenant_id,
        business_category_id=category_id,
        name=payload.name,
        slug=unique_slug,
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
        banner_mobile_url=payload.banner_mobile_url,
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
        "slug": getattr(r, "slug", None),
        "description": r.description,
        "owner": r.owner.full_name if r.owner else None,
        "owner_phone": r.owner.phone if r.owner else None,
        "owner_username": getattr(r.owner, "username", None) if r.owner else None,
        "has_password": bool(getattr(r.owner, "password_hash", None)) if r.owner else False,
        "phone": r.phone,
        "address": r.address,
        "city": r.city,
        "pincode": r.pincode,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lng) if lng is not None else None,
        "logo_url": r.logo_url,
        "list_banner_url": getattr(r, "list_banner_url", None),
        "banner_url": getattr(r, "banner_url", None),
        "banner_mobile_url": getattr(r, "banner_mobile_url", None),
        "business_category_id": r.business_category_id,
        "business_category": (
            r.business_category.name if r.business_category else None
        ),
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
    owner_username = data.pop("owner_username", None)
    owner_password = data.pop("owner_password", None)
    if "business_category_id" in data:
        category_id = data["business_category_id"]
        if category_id is not None and not db.query(CatalogCategory).filter(
            CatalogCategory.id == category_id,
            CatalogCategory.is_active == True,
        ).first():
            raise HTTPException(status_code=400, detail="Invalid business category")

    name_changed = "name" in data and data["name"] != restaurant.name
    for key, value in data.items():
        setattr(restaurant, key, value)

    if owner_name is not None and restaurant.owner:
        restaurant.owner.full_name = owner_name

    if restaurant.owner and (
        owner_username is not None or owner_password is not None
    ):
        apply_partner_credentials(
            db,
            restaurant.owner,
            username=owner_username,
            password=owner_password,
        )

    if name_changed or not getattr(restaurant, "slug", None):
        assign_restaurant_slug(
            db,
            restaurant,
            name=restaurant.name,
            force=bool(name_changed or not getattr(restaurant, "slug", None)),
        )

    db.commit()
    db.refresh(restaurant)
    return _admin_row(restaurant)
