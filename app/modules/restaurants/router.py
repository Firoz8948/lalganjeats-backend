from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.modules.banners import service as banner_service
from app.modules.restaurants import product_search, service
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
    service area (exact lat/lng vs tenant centre + matching zone range).
    """
    return service.list_public_restaurants(
        db,
        customer_lat=lat,
        customer_lng=lng,
        subcategory_id=subcategory_id,
    )


@router.get("/search")
def search_restaurants(
    q: str = Query(..., min_length=2, max_length=80, description="Dish or food name"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    category_id: int | None = Query(None, ge=1, description="Business category; Food when omitted"),
    db: Session = Depends(get_db),
):
    """Public search — restaurants that have a matching menu item near the customer."""
    return service.search_restaurants_by_dish(
        db,
        q=q,
        customer_lat=lat,
        customer_lng=lng,
        category_id=category_id,
    )


@router.get("/products/search")
def search_products(
    q: str = Query(..., min_length=2, max_length=80, description="Product keywords"),
    category_id: int = Query(..., ge=1, description="Business category (tab) to search in"),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(30, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Public search — products from deliverable stores of one category, best match first."""
    return product_search.search_products(
        db,
        q=q,
        category_id=category_id,
        customer_lat=lat,
        customer_lng=lng,
        limit=limit,
    )


@router.get("/subcategories/featured")
def featured_subcategories(
    category_id: int | None = Query(None, ge=1, description="Business category; Food when omitted"),
    db: Session = Depends(get_db),
):
    """Admin-curated home-row subcategories (featured + active) of one home tab."""
    return _subcategory_rows(db, category_id, featured_only=True)


@router.get("/categories/{category_id}/subcategories")
def category_subcategories(category_id: int, db: Session = Depends(get_db)):
    """Every active subcategory of a business category — featured ones first."""
    return _subcategory_rows(db, category_id, featured_only=False)


@router.get("/products")
def catalog_products(
    subcategory_id: int | None = Query(None, ge=1),
    category_id: int | None = Query(None, ge=1),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """
    Public — available products from stores that deliver to the customer:
    one subcategory, or every product of a business category ("All").
    """
    if subcategory_id is None and category_id is None:
        raise HTTPException(status_code=422, detail="subcategory_id or category_id is required")
    return product_search.list_catalog_products(
        db,
        category_id=category_id,
        subcategory_id=subcategory_id,
        customer_lat=lat,
        customer_lng=lng,
    )


def _subcategory_rows(db: Session, category_id: int | None, *, featured_only: bool) -> list[dict]:
    resolved = banner_service.resolve_category_id(db, category_id)
    filters = [
        CatalogSubcategory.category_id == resolved,
        CatalogSubcategory.is_active == True,  # noqa: E712
    ]
    if featured_only:
        filters.append(CatalogSubcategory.is_featured == True)  # noqa: E712
    ordering = [CatalogSubcategory.sort_order, CatalogSubcategory.name]
    if not featured_only:
        ordering.insert(0, CatalogSubcategory.is_featured.desc())
    rows = (
        db.query(
            CatalogSubcategory,
            func.count(MenuItem.id).label("product_count"),
            func.count(func.distinct(MenuItem.restaurant_id)).label("restaurant_count"),
        )
        .outerjoin(
            MenuItem,
            (MenuItem.business_subcategory_id == CatalogSubcategory.id)
            & (MenuItem.is_deleted == False)
            & (MenuItem.is_available == True),
        )
        .outerjoin(
            Restaurant,
            (Restaurant.id == MenuItem.restaurant_id)
            & (Restaurant.is_active == True)
            & (Restaurant.is_approved == True),
        )
        .filter(*filters)
        .group_by(CatalogSubcategory.id)
        .order_by(*ordering)
        .all()
    )
    return [
        {
            "id": item.id,
            "category_id": item.category_id,
            "name": item.name,
            "slug": item.slug,
            "image_url": item.image_url,
            "is_featured": bool(item.is_featured),
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
        .order_by(MenuCategory.sort_order, MenuCategory.id)
        .all()
    )
    cat_map = {c.id: c.name for c in categories}
    cat_order_map = {c.id: (c.sort_order if c.sort_order is not None else idx) for idx, c in enumerate(categories)}

    items = (
        db.query(MenuItem)
        .options(joinedload(MenuItem.variants))
        .filter(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.is_deleted == False,
        )
        .all()
    )
    items.sort(key=lambda i: (cat_order_map.get(i.category_id, 99999), i.sort_order or 0, i.id))
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
