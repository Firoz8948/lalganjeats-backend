from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.modules.restaurants import service
from app.modules.restaurants.models import (
    CatalogSubcategory,
    MenuItem,
    MenuCategory,
    Restaurant,
)

router = APIRouter(prefix="/api/v1/restaurants", tags=["Restaurants"])


@router.get("")
def list_restaurants(
    lat: float | None = Query(None, ge=-90, le=90, description="Customer latitude"),
    lng: float | None = Query(None, ge=-180, le=180, description="Customer longitude"),
    subcategory_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """
    Public list — approved & active restaurants within the customer's
    service area (exact lat/lng vs tenant centre + max active zone radius).
    """
    return service.list_public_restaurants(
        db,
        customer_lat=lat,
        customer_lng=lng,
        subcategory_id=subcategory_id,
    )


@router.get("/subcategories/featured")
def featured_subcategories(db: Session = Depends(get_db)):
    """Admin-curated home-row subcategories that currently have sellable items."""
    rows = (
        db.query(
            CatalogSubcategory,
            func.count(MenuItem.id).label("product_count"),
            func.count(func.distinct(MenuItem.restaurant_id)).label("restaurant_count"),
        )
        .join(MenuItem, MenuItem.business_subcategory_id == CatalogSubcategory.id)
        .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
        .filter(
            CatalogSubcategory.is_active == True,
            CatalogSubcategory.is_featured == True,
            MenuItem.is_deleted == False,
            MenuItem.is_available == True,
            Restaurant.is_active == True,
            Restaurant.is_approved == True,
        )
        .group_by(CatalogSubcategory.id)
        .order_by(CatalogSubcategory.sort_order, CatalogSubcategory.name)
        .all()
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "slug": item.slug,
            "product_count": product_count,
            "restaurant_count": restaurant_count,
        }
        for item, product_count, restaurant_count in rows
    ]


@router.get("/{restaurant_key}")
def get_restaurant(
    restaurant_key: str,
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """Public detail — single restaurant for menu page header (id or slug)."""
    return service.get_public_restaurant(
        db, restaurant_key, customer_lat=lat, customer_lng=lng
    )


@router.get("/{restaurant_key}/menu")
def get_restaurant_menu(restaurant_key: str, db: Session = Depends(get_db)):
    """Public menu — available (non-deleted) items for a restaurant (id or slug)."""
    restaurant = service.resolve_restaurant_key(db, restaurant_key)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    restaurant_id = restaurant.id

    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.restaurant_id == restaurant_id, MenuCategory.is_active == True)
        .order_by(MenuCategory.sort_order)
        .all()
    )
    cat_map = {c.id: c.name for c in categories}

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
    result = []
    for item in items:
        variants = [
            {
                "id": v.id,
                "label": v.label,
                "price": float(v.price),
                "original_price": float(v.original_price) if v.original_price else None,
                "is_available": v.is_available,
            }
            for v in sorted(
                (x for x in (item.variants or []) if not x.is_deleted),
                key=lambda x: (x.sort_order or 0, x.id or 0),
            )
        ]
        if (
            len(variants) == 1
            and variants[0]["label"].strip().lower() == "regular"
        ):
            variants = []
        available_prices = [v["price"] for v in variants if v["is_available"]]
        list_price = min(available_prices) if available_prices else float(item.price)
        result.append(
            {
                "id": item.id,
                "name": item.name,
                "description": item.description or "",
                "price": list_price,
                "original_price": (
                    float(item.original_price) if item.original_price else None
                ),
                "category": cat_map.get(item.category_id, "Other"),
                "category_id": item.category_id,
                "is_veg": item.is_veg,
                "is_bestseller": item.is_bestseller,
                "is_available": item.is_available,
                "image_url": item.image_url,
                "variants": variants,
            }
        )
    return result
