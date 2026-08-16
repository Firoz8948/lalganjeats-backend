from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session, joinedload

from decimal import Decimal

from app.core.storage import save_upload
from app.modules.admin.schemas import (
    AdminMenuItemCreate,
    AdminMenuItemUpdate,
    AdminMenuVariantCreate,
)
from app.modules.payments.pricing import calculate_display_price
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
        display = calculate_display_price(
            transfer,
            payment_settings.display_price_markup_percent,
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
                    f"MRP for {label} cannot be lower than calculated display "
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

    for existing in item.variants or []:
        existing.is_deleted = True
        existing.is_available = False
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
