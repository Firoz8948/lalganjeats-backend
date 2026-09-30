# backend/app/modules/shelves/service.py
from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.modules.restaurants.models import CatalogCategory, CatalogSubcategory, MenuItem, Restaurant
from app.modules.restaurants.product_search import (
    deliverable_products,
    product_load_options,
    sellable_product_filters,
    serialize_product,
)
from app.modules.restaurants.service import store_category_filter
from app.modules.shelves.models import ProductShelf, ProductShelfItem
from app.modules.shelves.schemas import ShelfSave

ADMIN_SEARCH_LIMIT = 40


def require_category(db: Session, category_id: int) -> int:
    if not db.query(CatalogCategory.id).filter(CatalogCategory.id == category_id).first():
        raise HTTPException(404, "Category not found")
    return category_id


def _ordered_shelves(db: Session, category_id: int, *, active_only: bool) -> list[ProductShelf]:
    query = (
        db.query(ProductShelf)
        .options(selectinload(ProductShelf.items))
        .filter(ProductShelf.business_category_id == category_id)
    )
    if active_only:
        query = query.filter(ProductShelf.is_active == True)  # noqa: E712
    return query.order_by(ProductShelf.sort_order, ProductShelf.id).all()


def _category_products(db: Session, category_id: int, tenant_id: int | None):
    query = (
        db.query(MenuItem)
        .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
        .filter(MenuItem.is_deleted == False, store_category_filter(db, category_id))  # noqa: E712
    )
    if tenant_id is not None:
        query = query.filter(Restaurant.tenant_id == tenant_id)
    return query


# ── Serialization ─────────────────────────────────────────

def _style(shelf: ProductShelf) -> dict:
    return {
        "id": shelf.id,
        "business_category_id": shelf.business_category_id,
        "title": shelf.title,
        "sort_order": shelf.sort_order,
        "section_bg_color": shelf.section_bg_color,
        "image_bg_color": shelf.image_bg_color,
        "card_bg_color": shelf.card_bg_color,
        "view_all_subcategory_id": shelf.view_all_subcategory_id,
        "is_active": bool(shelf.is_active),
    }


def _admin_product(item: MenuItem) -> dict:
    data = serialize_product(item)
    restaurant = item.restaurant
    return {
        "id": item.id,
        "name": item.name,
        "image_url": item.image_url,
        "price": data["price"],
        "subcategory": data["subcategory"],
        "restaurant_name": restaurant.name,
        "is_live": bool(
            item.is_available and not item.is_deleted and restaurant.is_active and restaurant.is_approved
        ),
    }


def _load_products(db: Session, ids: set[int], *extra_filters) -> dict[int, MenuItem]:
    if not ids:
        return {}
    rows = (
        db.query(MenuItem)
        .join(Restaurant, Restaurant.id == MenuItem.restaurant_id)
        .options(*product_load_options())
        .filter(MenuItem.id.in_(ids), *extra_filters)
        .all()
    )
    return {item.id: item for item in rows}


def serialize_admin_shelves(db: Session, shelves: list[ProductShelf]) -> list[dict]:
    products = _load_products(db, {row.menu_item_id for s in shelves for row in s.items})
    return [
        {
            **_style(shelf),
            "products": [
                _admin_product(products[row.menu_item_id])
                for row in shelf.items
                if row.menu_item_id in products
            ],
        }
        for shelf in shelves
    ]


# ── Admin ─────────────────────────────────────────────────

def list_admin_shelves(db: Session, category_id: int) -> list[dict]:
    return serialize_admin_shelves(db, _ordered_shelves(db, category_id, active_only=False))


def _apply(db: Session, shelf: ProductShelf, payload: ShelfSave, tenant_id: int | None) -> None:
    category_id = shelf.business_category_id
    if payload.view_all_subcategory_id is not None:
        belongs = (
            db.query(CatalogSubcategory.id)
            .filter(
                CatalogSubcategory.id == payload.view_all_subcategory_id,
                CatalogSubcategory.category_id == category_id,
            )
            .first()
        )
        if not belongs:
            raise HTTPException(400, "View-all subcategory must belong to this category")

    product_ids = list(dict.fromkeys(payload.product_ids))
    if product_ids:
        allowed = {
            row[0]
            for row in _category_products(db, category_id, tenant_id)
            .filter(MenuItem.id.in_(product_ids))
            .with_entities(MenuItem.id)
            .all()
        }
        unknown = [pid for pid in product_ids if pid not in allowed]
        if unknown:
            raise HTTPException(400, f"Products not available in this category: {unknown}")

    shelf.title = payload.title.strip()
    shelf.sort_order = payload.sort_order
    shelf.section_bg_color = payload.section_bg_color.lower()
    shelf.image_bg_color = payload.image_bg_color.lower()
    shelf.card_bg_color = payload.card_bg_color.lower()
    shelf.view_all_subcategory_id = payload.view_all_subcategory_id
    shelf.is_active = payload.is_active
    if shelf.id is not None:
        # The unit of work inserts before it deletes; drop old rows first so
        # re-saving the same products cannot hit uq_product_shelf_item.
        shelf.items.clear()
        db.flush()
    shelf.items = [
        ProductShelfItem(menu_item_id=pid, position=index)
        for index, pid in enumerate(product_ids)
    ]


def create_shelf(db: Session, category_id: int, payload: ShelfSave, tenant_id: int | None) -> dict:
    shelf = ProductShelf(business_category_id=require_category(db, category_id))
    _apply(db, shelf, payload, tenant_id)
    db.add(shelf)
    db.commit()
    return serialize_admin_shelves(db, [shelf])[0]


def _get_shelf(db: Session, shelf_id: int) -> ProductShelf:
    shelf = db.get(ProductShelf, shelf_id)
    if not shelf:
        raise HTTPException(404, "Section not found")
    return shelf


def update_shelf(db: Session, shelf_id: int, payload: ShelfSave, tenant_id: int | None) -> dict:
    shelf = _get_shelf(db, shelf_id)
    _apply(db, shelf, payload, tenant_id)
    db.commit()
    return serialize_admin_shelves(db, [shelf])[0]


def delete_shelf(db: Session, shelf_id: int) -> None:
    db.delete(_get_shelf(db, shelf_id))
    db.commit()


def search_admin_products(
    db: Session, category_id: int, q: str, tenant_id: int | None
) -> list[dict]:
    query = _category_products(db, require_category(db, category_id), tenant_id).options(
        *product_load_options()
    )
    term = (q or "").strip()
    if term:
        query = query.filter(MenuItem.name.ilike(f"%{term}%"))
    items = query.order_by(MenuItem.name).limit(ADMIN_SEARCH_LIMIT).all()
    return [_admin_product(item) for item in items]


# ── Customer ──────────────────────────────────────────────

def list_public_shelves(
    db: Session, category_id: int, customer_lat: float | None, customer_lng: float | None
) -> list[dict]:
    """Active sections with the products that can be delivered to the customer; empty ones are left out."""
    if customer_lat is None or customer_lng is None:
        return []
    shelves = _ordered_shelves(db, category_id, active_only=True)
    ids = {row.menu_item_id for shelf in shelves for row in shelf.items}
    products = _load_products(db, ids, *sellable_product_filters())
    deliverable = {
        item.id: item
        for item in deliverable_products(list(products.values()), customer_lat, customer_lng)
    }

    result = []
    for shelf in shelves:
        items = [deliverable[row.menu_item_id] for row in shelf.items if row.menu_item_id in deliverable]
        if items:
            result.append({**_style(shelf), "products": [serialize_product(item) for item in items]})
    return result
