from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from decimal import Decimal

from app.core.storage import save_upload
from app.modules.admin.schemas import AdminMenuItemCreate
from app.modules.payments.pricing import calculate_display_price
from app.modules.payments.service import ensure_payment_settings
from app.modules.restaurants.models import (
    CatalogSubcategory,
    MenuCategory,
    MenuItem,
    Restaurant,
)


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
        .filter(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_deleted == False,
        )
        .order_by(MenuItem.sort_order, MenuItem.id)
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description or "",
            "price": float(item.price),
            "actual_price": float(item.actual_price) if item.actual_price else None,
            "original_price": (
                float(item.original_price) if item.original_price else None
            ),
            "category": cat_map.get(item.category_id, "Other"),
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
        }
        for item in items
    ]


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

    payment_settings = ensure_payment_settings(db)
    transfer_price = Decimal(str(payload.actual_price))
    display_price = calculate_display_price(
        transfer_price,
        payment_settings.display_price_markup_percent,
    )
    mrp = (
        Decimal(str(payload.original_price))
        if payload.original_price is not None
        else None
    )
    if mrp is not None and mrp < display_price:
        raise HTTPException(
            status_code=400,
            detail=(
                f"MRP cannot be lower than calculated display price "
                f"₹{display_price:.2f}."
            ),
        )

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
        price=display_price,
        actual_price=transfer_price,
        original_price=mrp,
        is_veg=payload.is_veg,
        is_bestseller=payload.is_bestseller,
        is_available=True,
        is_deleted=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "price": float(item.price),
        "actual_price": float(item.actual_price),
        "original_price": (
            float(item.original_price) if item.original_price else None
        ),
        "category": category.name,
        "category_id": item.category_id,
        "subcategory_id": item.business_subcategory_id,
        "subcategory": subcategory.name if subcategory else None,
        "is_veg": item.is_veg,
        "is_bestseller": item.is_bestseller,
        "is_available": item.is_available,
    }


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
        "home_banner_desktop": "home_banners/desktop",
        "home_banner_mobile": "home_banners/mobile",
    }
    if purpose not in folder_map:
        raise HTTPException(
            status_code=400,
            detail=(
                "purpose must be 'list_banner', 'menu_banner', "
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
