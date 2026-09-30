# backend/app/modules/restaurants/product_search.py
"""Keyword product search inside one business category (e.g. Grocery tab)."""
import re

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.core.schedule_hours import format_opens_at
from app.modules.restaurants.models import (
    CatalogSubcategory,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    Restaurant,
)
from app.modules.restaurants.service import (
    DistanceCache,
    _restaurant_visible_for_customer,
    store_category_filter,
)
from app.modules.superadmin.models import Tenant

MAX_CANDIDATES = 500


def _tokens(query: str) -> list[str]:
    words = [w for w in re.split(r"[^\w]+", query.lower()) if w]
    long_words = [w for w in words if len(w) >= 2]
    return long_words or words


def _score(query: str, tokens: list[str], name: str, groups: str, description: str) -> float:
    """Whole-query matches on the name rank highest, then per-keyword hits."""
    score = 0.0
    if name == query:
        score += 1000
    elif name.startswith(query):
        score += 600
    elif re.search(r"\b" + re.escape(query), name):
        score += 450
    elif query in name:
        score += 350

    matched = 0
    for token in tokens:
        if re.search(r"\b" + re.escape(token), name):
            score += 40
        elif token in name:
            score += 25
        elif token in groups:
            score += 15
        elif token in description:
            score += 8
        else:
            continue
        matched += 1
    if tokens:
        score += 100 * matched / len(tokens)
    return score


def _list_offer(item: MenuItem) -> tuple[float, float | None, MenuItemVariant | None]:
    """Price, MRP and the variant a one-tap "Buy" adds (the cheapest available one)."""
    variants = [v for v in (item.variants or []) if not v.is_deleted and v.is_available]
    if variants:
        cheapest = min(variants, key=lambda v: float(v.price))
        mrp = cheapest.original_price or item.original_price
        return float(cheapest.price), float(mrp) if mrp else None, cheapest
    return float(item.price), float(item.original_price) if item.original_price else None, None


def search_products(
    db: Session,
    *,
    q: str,
    category_id: int,
    customer_lat: float | None,
    customer_lng: float | None,
    limit: int = 30,
) -> list[dict]:
    query = re.sub(r"\s+", " ", (q or "").strip().lower())
    if len(query) < 2 or customer_lat is None or customer_lng is None:
        return []
    tokens = _tokens(query)
    if not tokens:
        return []

    keyword_filters = []
    for token in tokens:
        like = f"%{token}%"
        keyword_filters += [
            MenuItem.name.ilike(like),
            MenuItem.description.ilike(like),
            CatalogSubcategory.name.ilike(like),
            MenuCategory.name.ilike(like),
        ]

    rows = (
        db.query(MenuItem, CatalogSubcategory.name, MenuCategory.name)
        .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
        .outerjoin(CatalogSubcategory, CatalogSubcategory.id == MenuItem.business_subcategory_id)
        .outerjoin(MenuCategory, MenuCategory.id == MenuItem.category_id)
        .options(*product_load_options())
        .filter(
            store_category_filter(db, category_id),
            Restaurant.is_active == True,  # noqa: E712
            Restaurant.is_approved == True,  # noqa: E712
            MenuItem.is_deleted == False,  # noqa: E712
            MenuItem.is_available == True,  # noqa: E712
            or_(*keyword_filters),
        )
        .limit(MAX_CANDIDATES)
        .all()
    )

    dist_cache: DistanceCache = {}
    visible_by_restaurant: dict[int, bool] = {}
    scored: list[tuple[float, MenuItem, str | None]] = []
    for item, subcategory_name, menu_category_name in rows:
        restaurant = item.restaurant
        visible = visible_by_restaurant.get(restaurant.id)
        if visible is None:
            visible = _restaurant_visible_for_customer(
                restaurant, customer_lat, customer_lng, dist_cache
            )
            visible_by_restaurant[restaurant.id] = visible
        if not visible:
            continue
        groups = f"{subcategory_name or ''} {menu_category_name or ''}".lower()
        score = _score(
            query, tokens, item.name.lower(), groups, (item.description or "").lower()
        )
        if score > 0:
            scored.append((score, item, subcategory_name or menu_category_name))

    scored.sort(key=lambda s: (-s[0], not s[1].restaurant.is_open, len(s[1].name), s[1].name.lower()))

    return [
        {**serialize_product(item, group), "score": round(score, 1)}
        for score, item, group in scored[:limit]
    ]


def product_load_options() -> tuple:
    """Eager loads every product listing needs (price, cart line, store visibility)."""
    return (
        selectinload(MenuItem.variants),
        selectinload(MenuItem.category),
        selectinload(MenuItem.business_subcategory),
        selectinload(MenuItem.restaurant).selectinload(Restaurant.tenant).selectinload(Tenant.zones),
        selectinload(MenuItem.restaurant).selectinload(Restaurant.tenant).selectinload(Tenant.delivery_exceptions),
    )


def serialize_product(item: MenuItem, group: str | None = None) -> dict:
    restaurant = item.restaurant
    price, original_price, variant = _list_offer(item)
    if group is None and item.business_subcategory is not None:
        group = item.business_subcategory.name
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "price": price,
        "original_price": original_price,
        "variant_id": variant.id if variant else None,
        "variant_label": variant.label if variant else None,
        "category": item.category.name if item.category else (group or ""),
        "image_url": item.image_url,
        "is_veg": item.is_veg,
        "subcategory": group,
        "subcategory_id": item.business_subcategory_id,
        "restaurant": {
            "id": restaurant.id,
            "slug": restaurant.slug,
            "name": restaurant.name,
            "business_category_id": restaurant.business_category_id,
            "is_open": bool(restaurant.is_open),
            "opens_at_label": (
                None if restaurant.is_open else format_opens_at(restaurant.opening_time)
            ),
        },
    }


def list_catalog_products(
    db: Session,
    *,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    customer_lat: float | None,
    customer_lng: float | None,
    limit: int = 300,
) -> list[dict]:
    """
    Available products from stores that deliver to the customer: one catalog
    subcategory when subcategory_id is given, otherwise every product of the
    business category (the "All" tab).
    """
    if customer_lat is None or customer_lng is None:
        return []

    filters = []
    if subcategory_id is not None:
        subcategory = (
            db.query(CatalogSubcategory)
            .filter(CatalogSubcategory.id == subcategory_id, CatalogSubcategory.is_active == True)  # noqa: E712
            .first()
        )
        if not subcategory:
            return []
        category_id = subcategory.category_id
        filters.append(MenuItem.business_subcategory_id == subcategory.id)
    elif category_id is None:
        return []

    items = (
        db.query(MenuItem)
        .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
        .options(*product_load_options())
        .filter(
            *filters,
            *sellable_product_filters(),
            store_category_filter(db, category_id),
        )
        .all()
    )

    visible_items = deliverable_products(items, customer_lat, customer_lng)
    visible_items.sort(
        key=lambda i: (
            not i.restaurant.is_open,
            not i.is_bestseller,
            i.sort_order or 0,
            i.name.lower(),
        )
    )
    return [serialize_product(item) for item in visible_items[:limit]]


def sellable_product_filters() -> tuple:
    """Live product of an active, approved store. Callers must join Restaurant."""
    return (
        Restaurant.is_active == True,  # noqa: E712
        Restaurant.is_approved == True,  # noqa: E712
        MenuItem.is_deleted == False,  # noqa: E712
        MenuItem.is_available == True,  # noqa: E712
    )


def deliverable_products(
    items: list[MenuItem], customer_lat: float, customer_lng: float
) -> list[MenuItem]:
    """Keep products whose store delivers to the customer, preserving order."""
    dist_cache: DistanceCache = {}
    visible_by_restaurant: dict[int, bool] = {}
    visible = []
    for item in items:
        restaurant = item.restaurant
        if restaurant.id not in visible_by_restaurant:
            visible_by_restaurant[restaurant.id] = _restaurant_visible_for_customer(
                restaurant, customer_lat, customer_lng, dist_cache
            )
        if visible_by_restaurant[restaurant.id]:
            visible.append(item)
    return visible
