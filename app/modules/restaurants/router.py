from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.restaurants import service
from app.modules.restaurants.models import MenuItem, MenuCategory

router = APIRouter(prefix="/api/v1/restaurants", tags=["Restaurants"])


@router.get("")
def list_restaurants(db: Session = Depends(get_db)):
    """Public list — approved & active restaurants for home page."""
    return service.list_public_restaurants(db)


@router.get("/{restaurant_id}")
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    """Public detail — single restaurant for menu page header."""
    return service.get_public_restaurant(db, restaurant_id)


@router.get("/{restaurant_id}/menu")
def get_restaurant_menu(restaurant_id: int, db: Session = Depends(get_db)):
    """Public menu — available (non-deleted) items for a restaurant."""
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.restaurant_id == restaurant_id, MenuCategory.is_active == True)
        .order_by(MenuCategory.sort_order)
        .all()
    )
    cat_map = {c.id: c.name for c in categories}

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
            "id":             item.id,
            "name":           item.name,
            "description":    item.description or "",
            "price":          float(item.price),
            "original_price": float(item.original_price) if item.original_price else None,
            "category":       cat_map.get(item.category_id, "Other"),
            "category_id":    item.category_id,
            "is_veg":         item.is_veg,
            "is_bestseller":  item.is_bestseller,
            "is_available":   item.is_available,
            "image_url":      item.image_url,
        }
        for item in items
    ]
