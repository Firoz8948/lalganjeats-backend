from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session, joinedload

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.security import create_access_token
from app.core.storage import save_upload
from app.modules.admin.models import ImpersonationSession
from app.modules.admin.schemas import (
    AdminMenuItemCreate,
    AdminMenuItemUpdate,
    AdminMenuVariantCreate,
)
from app.modules.payments.pricing import resolve_display_price
from app.modules.payments.service import ensure_payment_settings
from app.modules.restaurants.models import (
    CatalogSubcategory,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    Restaurant,
)


_KNOWN_LABELS = {
    "half": "Half",
    "full": "Full",
    "regular": "Regular",
}

IMPERSONATION_TTL_MINUTES = 30
IMPERSONATION_PURPOSE = "restaurant_admin_impersonation"


def validate_impersonation_target(admin, restaurant: Restaurant):
    """Return the owner only when the tenant admin may enter this restaurant."""
    if admin.role != "admin" or admin.tenant_id is None:
        raise HTTPException(403, "Tenant admin access required")
    if restaurant.tenant_id != admin.tenant_id:
        # Avoid exposing another tenant's restaurant IDs.
        raise HTTPException(404, "Restaurant not found")
    if not restaurant.is_active:
        raise HTTPException(400, "Restaurant is inactive")
    if not getattr(restaurant, "is_approved", False):
        raise HTTPException(400, "Restaurant is not approved")
    owner = getattr(restaurant, "owner", None)
    if (
        owner is None
        or owner.role != "restaurant_owner"
        or not owner.is_active
        or owner.tenant_id != admin.tenant_id
    ):
        raise HTTPException(400, "Restaurant owner is inactive or unavailable")
    return owner


def assert_live_impersonation_session(
    db: Session,
    target_user,
    expected_type: str | None = None,
) -> ImpersonationSession | None:
    """Reject ended, expired, or scope-mismatched impersonation tokens."""
    jti = getattr(target_user, "impersonation_session_id", None)
    impersonation_type = getattr(target_user, "impersonation_type", None)
    impersonating = bool(
        getattr(target_user, "impersonated_by", None)
        or impersonation_type
        or jti
    )
    if not impersonating:
        return None
    if (
        not jti
        or impersonation_type not in {"restaurant", "delivery_partner"}
        or (expected_type is not None and impersonation_type != expected_type)
    ):
        raise HTTPException(401, "Impersonation session is invalid")

    session = (
        db.query(ImpersonationSession)
        .filter(ImpersonationSession.jti == jti)
        .first()
    )
    now = datetime.now(timezone.utc)
    restaurant_id = getattr(target_user, "impersonated_restaurant_id", None)
    expires_at = session.expires_at if session else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if (
        session is None
        or session.ended_at is not None
        or expires_at is None
        or expires_at <= now
        or session.owner_user_id != target_user.id
        or getattr(session, "purpose", None)
        != getattr(target_user, "impersonation_purpose", None)
        or (
            impersonation_type == "restaurant"
            and (
                restaurant_id is None
                or session.restaurant_id != int(restaurant_id)
            )
        )
        or (
            impersonation_type == "delivery_partner"
            and session.restaurant_id is not None
        )
    ):
        raise HTTPException(401, "Impersonation session has ended or expired")
    return session


def end_impersonation_session(db: Session, current_user) -> dict:
    """Mark the caller's live admin impersonation session as ended."""
    session = assert_live_impersonation_session(db, current_user)
    if session is None:
        raise HTTPException(400, "No active impersonation session")
    if session.ended_at is None:
        session.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session)
    ended = session.ended_at
    if ended is not None and ended.tzinfo is None:
        ended = ended.replace(tzinfo=timezone.utc)
    return {
        "ok": True,
        "ended_at": ended.isoformat() if ended else None,
    }


def impersonate_restaurant(
    db: Session,
    restaurant_id: int,
    admin,
    request: Request | None = None,
) -> dict:
    restaurant = (
        db.query(Restaurant)
        .options(joinedload(Restaurant.owner))
        .filter(Restaurant.id == restaurant_id)
        .first()
    )
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    owner = validate_impersonation_target(admin, restaurant)

    jti = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_TTL_MINUTES)
    ip_address = None
    user_agent = None
    if request is not None:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    audit = ImpersonationSession(
        jti=jti,
        admin_user_id=admin.id,
        owner_user_id=owner.id,
        restaurant_id=restaurant.id,
        tenant_id=admin.tenant_id,
        purpose=IMPERSONATION_PURPOSE,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(audit)
    db.commit()

    token = create_access_token(
        {
            "sub": str(owner.id),
            "role": "restaurant_owner",
            "tenant_id": admin.tenant_id,
            "restaurant_id": restaurant.id,
            "impersonated_by": admin.id,
            "impersonation_type": "restaurant",
            "impersonation_session_id": jti,
            "purpose": IMPERSONATION_PURPOSE,
        },
        expires_delta=timedelta(minutes=IMPERSONATION_TTL_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "restaurant_owner",
        "user_id": owner.id,
        "full_name": owner.full_name,
        "phone": owner.phone,
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "impersonated_by": admin.id,
        "impersonation_session_id": jti,
        "redirect_to": "/hotel-portal/dashboard",
    }


def normalize_variant_label(label: str) -> str:
    cleaned = " ".join((label or "").strip().split())
    if not cleaned:
        raise HTTPException(400, "Variant label is required")
    key = cleaned.lower()
    return _KNOWN_LABELS.get(key, cleaned)


def _serialize_variants(item: MenuItem) -> list[dict]:
    rows = [
        v
        for v in (item.variants or [])
        if not getattr(v, "is_deleted", False)
    ]
    rows.sort(key=lambda v: (v.sort_order or 0, v.id or 0))
    # A sole Regular row is the internal compatibility price, not a customer-
    # visible/admin-entered variant.
    if len(rows) == 1 and rows[0].label.strip().lower() == "regular":
        return []
    return [
        {
            "id": v.id,
            "label": v.label,
            "price": float(v.price),
            "actual_price": float(v.actual_price),
            "original_price": float(v.original_price) if v.original_price else None,
            "is_available": v.is_available,
            "sort_order": v.sort_order or 0,
        }
        for v in rows
    ]


def _serialize_menu_item(item: MenuItem, category_name: str) -> dict:
    variants = _serialize_variants(item)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "price": float(item.price),
        "actual_price": float(item.actual_price) if item.actual_price else None,
        "original_price": (
            float(item.original_price) if item.original_price else None
        ),
        "category": category_name,
        "category_id": item.category_id,
        "subcategory_id": item.business_subcategory_id,
        "subcategory": (
            item.business_subcategory.name
            if item.business_subcategory
            else None
        ),
        "is_veg": item.is_veg,
        "is_bestseller": item.is_bestseller,
        "is_available": item.is_available,
        "image_url": item.image_url,
        "variants": variants,
    }


def approve_restaurant(db: Session, restaurant_id: int):
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id
    ).first()
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    restaurant.is_approved = True
    db.commit()
    return {"message": "Restaurant approved"}


def get_restaurant_menu(db: Session, restaurant_id: int):
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.restaurant_id == restaurant_id)
        .all()
    )
    cat_map = {category.id: category.name for category in categories}

    items = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.variants))
        .filter(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_deleted == False,
        )
        .order_by(MenuItem.sort_order, MenuItem.id)
        .all()
    )
    return [
        _serialize_menu_item(item, cat_map.get(item.category_id, "Other"))
        for item in items
    ]


def _resolve_variant_inputs(
    payload: AdminMenuItemCreate,
) -> list[AdminMenuVariantCreate]:
    if payload.variants:
        return payload.variants
    if payload.actual_price is None:
        raise HTTPException(
            400,
            "Provide seller transfer price or at least one variant",
        )
    return [
        AdminMenuVariantCreate(
            label="Regular",
            actual_price=payload.actual_price,
            price=payload.price,
            original_price=payload.original_price,
        )
    ]


def _priced_variant_inputs(
    db: Session,
    payload: AdminMenuItemCreate,
) -> list[tuple[str, Decimal, Decimal, Decimal | None, int]]:
    payment_settings = ensure_payment_settings(db)
    variant_inputs = _resolve_variant_inputs(payload)
    priced: list[tuple[str, Decimal, Decimal, Decimal | None, int]] = []
    seen_labels: set[str] = set()
    for index, raw in enumerate(variant_inputs):
        label = normalize_variant_label(raw.label)
        key = label.lower()
        if key in seen_labels:
            raise HTTPException(400, f"Duplicate variant label: {label}")
        seen_labels.add(key)

        transfer = Decimal(str(raw.actual_price))
        display = resolve_display_price(
            transfer,
            payment_settings.display_price_markup_percent,
            raw.price,
        )
        mrp = (
            Decimal(str(raw.original_price))
            if raw.original_price is not None
            else None
        )
        if mrp is not None and mrp < display:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"MRP for {label} cannot be lower than display "
                    f"price ₹{display:.2f}."
                ),
            )
        priced.append((label, transfer, display, mrp, index))
    if not priced:
        raise HTTPException(400, "At least one variant is required")
    return priced


def add_menu_item(
    db: Session,
    restaurant_id: int,
    payload: AdminMenuItemCreate,
):
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id
    ).first()
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")

    priced_variants = _priced_variant_inputs(db, payload)

    # Parent row mirrors the first (default) variant for backward compatibility.
    default_label, default_transfer, default_display, default_mrp, _ = priced_variants[0]

    subcategory = None
    if payload.subcategory_id is not None:
        subcategory = db.query(CatalogSubcategory).filter(
            CatalogSubcategory.id == payload.subcategory_id,
            CatalogSubcategory.is_active == True,
        ).first()
        if not subcategory:
            raise HTTPException(status_code=400, detail="Invalid subcategory")
        if (
            restaurant.business_category_id is not None
            and subcategory.category_id != restaurant.business_category_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Subcategory does not belong to the restaurant category",
            )
    menu_category_name = subcategory.name if subcategory else payload.category_name

    category = (
        db.query(MenuCategory)
        .filter(
            MenuCategory.restaurant_id == restaurant_id,
            MenuCategory.name == menu_category_name,
        )
        .first()
    )
    if not category:
        category = MenuCategory(
            restaurant_id=restaurant_id,
            name=menu_category_name,
            is_active=True,
        )
        db.add(category)
        db.flush()

    item = MenuItem(
        restaurant_id=restaurant_id,
        category_id=category.id,
        business_subcategory_id=(
            subcategory.id if subcategory is not None else None
        ),
        name=payload.name,
        description=payload.description,
        image_url=payload.image_url,
        price=default_display,
        actual_price=default_transfer,
        original_price=default_mrp,
        is_veg=payload.is_veg,
        is_bestseller=payload.is_bestseller,
        is_available=True,
        is_deleted=False,
    )
    db.add(item)
    db.flush()

    for label, transfer, display, mrp, sort_order in priced_variants:
        db.add(
            MenuItemVariant(
                menu_item_id=item.id,
                label=label,
                price=display,
                actual_price=transfer,
                original_price=mrp,
                sort_order=sort_order,
                is_available=True,
                is_deleted=False,
            )
        )

    db.commit()
    db.refresh(item)
    item = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.variants))
        .filter(MenuItem.id == item.id)
        .first()
    )
    return _serialize_menu_item(item, category.name)


def update_menu_item(
    db: Session,
    restaurant_id: int,
    item_id: int,
    payload: AdminMenuItemUpdate,
):
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id
    ).first()
    item = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.variants))
        .filter(
            MenuItem.id == item_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_deleted == False,
        )
        .first()
    )
    if not restaurant or not item:
        raise HTTPException(404, "Item not found")

    subcategory = None
    if payload.subcategory_id is not None:
        subcategory = db.query(CatalogSubcategory).filter(
            CatalogSubcategory.id == payload.subcategory_id,
            CatalogSubcategory.is_active == True,
        ).first()
        if not subcategory:
            raise HTTPException(400, "Invalid subcategory")
        if (
            restaurant.business_category_id is not None
            and subcategory.category_id != restaurant.business_category_id
        ):
            raise HTTPException(
                400,
                "Subcategory does not belong to the restaurant category",
            )

    category_name = subcategory.name if subcategory else payload.category_name
    category = db.query(MenuCategory).filter(
        MenuCategory.restaurant_id == restaurant_id,
        MenuCategory.name == category_name,
    ).first()
    if not category:
        category = MenuCategory(
            restaurant_id=restaurant_id,
            name=category_name,
            is_active=True,
        )
        db.add(category)
        db.flush()

    priced_variants = _priced_variant_inputs(db, payload)
    _, default_transfer, default_display, default_mrp, _ = priced_variants[0]
    item.category_id = category.id
    item.business_subcategory_id = subcategory.id if subcategory else None
    item.name = payload.name
    item.description = payload.description
    item.image_url = payload.image_url
    item.price = default_display
    item.actual_price = default_transfer
    item.original_price = default_mrp
    item.is_veg = payload.is_veg
    item.is_bestseller = payload.is_bestseller

    # Upsert by label. Delete+insert of the same label violates
    # uq_menu_item_variant_label and rolls the whole item update back.
    existing_by_label = {
        (v.label or "").strip().lower(): v
        for v in (item.variants or [])
    }
    keep_ids: set[int] = set()
    for label, transfer, display, mrp, sort_order in priced_variants:
        key = label.strip().lower()
        row = existing_by_label.get(key)
        if row:
            row.label = label
            row.price = display
            row.actual_price = transfer
            row.original_price = mrp
            row.sort_order = sort_order
            row.is_available = True
            row.is_deleted = False
            if row.id is not None:
                keep_ids.add(row.id)
        else:
            db.add(
                MenuItemVariant(
                    menu_item_id=item.id,
                    label=label,
                    price=display,
                    actual_price=transfer,
                    original_price=mrp,
                    sort_order=sort_order,
                    is_available=True,
                    is_deleted=False,
                )
            )
    for row in item.variants or []:
        if row.id not in keep_ids:
            row.is_deleted = True
            row.is_available = False

    db.commit()
    db.expire_all()
    refreshed = (
        db.query(MenuItem)
        .options(
            joinedload(MenuItem.variants),
            joinedload(MenuItem.business_subcategory),
        )
        .filter(MenuItem.id == item.id)
        .first()
    )
    return _serialize_menu_item(refreshed, category.name)


def toggle_menu_item(db: Session, restaurant_id: int, item_id: int):
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant_id,
        MenuItem.is_deleted == False,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    item.is_available = not item.is_available
    db.commit()
    return {"id": item.id, "is_available": item.is_available}


def delete_menu_item(db: Session, restaurant_id: int, item_id: int):
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant_id,
        MenuItem.is_deleted == False,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    item.is_deleted = True
    db.commit()
    return {"message": "Deleted"}


def set_restaurant_banner(db: Session, restaurant_id: int, payload: dict):
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id
    ).first()
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    restaurant.banner_url = payload.get("banner_url")
    db.commit()
    return {"message": "Banner updated", "banner_url": restaurant.banner_url}


async def upload_restaurant_image(
    request: Request,
    file: UploadFile,
    purpose: str,
):
    folder_map = {
        "list_banner": "restaurants/list_banner",
        "menu_banner": "restaurants/menu_banner",
        "menu_banner_mobile": "restaurants/menu_banner_mobile",
        "menu_item": "restaurants/menu_items",
        "home_banner_desktop": "home_banners/desktop",
        "home_banner_mobile": "home_banners/mobile",
    }
    if purpose not in folder_map:
        raise HTTPException(
            status_code=400,
            detail=(
                "purpose must be 'list_banner', 'menu_banner', "
                "'menu_banner_mobile', 'menu_item', "
                "'home_banner_desktop', or 'home_banner_mobile'"
            ),
        )

    max_bytes = (
        5 * 1024 * 1024
        if purpose.startswith("home_banner")
        else 2 * 1024 * 1024
    )
    relative_path = await save_upload(
        file,
        folder_map[purpose],
        max_bytes=max_bytes,
    )
    base = str(request.base_url).rstrip("/")
    return {
        "url": (
            relative_path
            if relative_path.startswith("http")
            else f"{base}{relative_path}"
        ),
        "path": relative_path,
        "purpose": purpose,
    }
