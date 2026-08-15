import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.restaurants.models import CatalogCategory, CatalogSubcategory


FOOD_SUBCATEGORIES = [
    "Fast Food", "Burgers", "Pizza", "Sandwiches", "Wraps & Rolls", "Momos",
    "Pasta", "Noodles", "Chowmein", "Manchurian", "Spring Rolls",
    "French Fries", "Snacks", "Samosa", "Kachori", "Pakora", "Chaat",
    "Golgappa / Pani Puri", "Aloo Tikki", "Dahi Bhalla", "Pav Bhaji",
    "Vada Pav", "Dosa", "Idli", "Uttapam", "South Indian", "North Indian",
    "Thali", "Biryani", "Pulao", "Rice", "Fried Rice", "Dal", "Roti & Naan",
    "Paratha", "Paneer Dishes", "Chicken Dishes", "Mutton Dishes",
    "Fish & Seafood", "Tandoori", "Kebab", "Tikka", "Korma", "Curry",
    "Chinese", "Indian Chinese", "Mughlai", "Punjabi", "Awadhi",
    "Street Food", "Bakery", "Cakes", "Pastries", "Donuts", "Cookies",
    "Ice Cream", "Kulfi", "Desserts", "Mithai / Sweets", "Gulab Jamun",
    "Jalebi", "Rasmalai", "Halwa", "Fruit Desserts", "Lassi", "Milkshakes",
    "Smoothies", "Fresh Juice", "Fruit Juice", "Mocktails", "Cold Drinks",
    "Soft Drinks", "Soda", "Lemonade", "Shikanji", "Tea", "Coffee",
    "Cold Coffee", "Hot Beverages", "Packaged Beverages", "Beverages",
    "Combos", "Meal Combos", "Family Combos", "Party Combos",
    "Burger Combos", "Pizza Combos", "Biryani Combos", "Chinese Combos",
    "Breakfast Combos", "Lunch Combos", "Dinner Combos", "Kids Meals",
    "Family Meals", "Sharing Platters", "Snacks & Beverages", "Veg Specials",
    "Non-Veg Specials", "Jain Food", "Healthy Food", "Diet Food",
]


def slugify(value: str) -> str:
    value = value.strip().lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def normalize_subcategory_names(names: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            result.append(name)
    return result


def ensure_default_catalog(db: Session) -> None:
    restaurant = (
        db.query(CatalogCategory)
        .filter(CatalogCategory.slug == "restaurant")
        .first()
    )
    if not restaurant:
        restaurant = CatalogCategory(
            name="Restaurant", slug="restaurant", sort_order=1, is_active=True
        )
        db.add(restaurant)
        db.flush()

    grocery = (
        db.query(CatalogCategory)
        .filter(CatalogCategory.slug == "grocery")
        .first()
    )
    if not grocery:
        db.add(
            CatalogCategory(
                name="Grocery", slug="grocery", sort_order=2, is_active=True
            )
        )

    existing = {
        item.slug
        for item in db.query(CatalogSubcategory)
        .filter(CatalogSubcategory.category_id == restaurant.id)
        .all()
    }
    for order, name in enumerate(
        normalize_subcategory_names(FOOD_SUBCATEGORIES), start=1
    ):
        slug = slugify(name)
        if slug not in existing:
            db.add(
                CatalogSubcategory(
                    category_id=restaurant.id,
                    name=name,
                    slug=slug,
                    sort_order=order,
                    is_active=True,
                )
            )
    db.commit()


def list_categories(db: Session):
    ensure_default_catalog(db)
    return (
        db.query(CatalogCategory)
        .order_by(CatalogCategory.sort_order, CatalogCategory.name)
        .all()
    )


def create_category(db: Session, name: str):
    clean = name.strip()
    slug = slugify(clean)
    if not clean or not slug:
        raise HTTPException(400, "Category name is required")
    if db.query(CatalogCategory).filter(CatalogCategory.slug == slug).first():
        raise HTTPException(400, "Category already exists")
    category = CatalogCategory(name=clean, slug=slug, is_active=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_subcategories(db: Session, category_id: int):
    return (
        db.query(CatalogSubcategory)
        .filter(CatalogSubcategory.category_id == category_id)
        .order_by(CatalogSubcategory.sort_order, CatalogSubcategory.name)
        .all()
    )


def create_subcategory(db: Session, category_id: int, name: str):
    category = db.query(CatalogCategory).filter(
        CatalogCategory.id == category_id
    ).first()
    if not category:
        raise HTTPException(404, "Category not found")
    clean = name.strip()
    slug = slugify(clean)
    if not clean or not slug:
        raise HTTPException(400, "Subcategory name is required")
    exists = db.query(CatalogSubcategory).filter(
        CatalogSubcategory.category_id == category_id,
        CatalogSubcategory.slug == slug,
    ).first()
    if exists:
        raise HTTPException(400, "Subcategory already exists")
    item = CatalogSubcategory(
        category_id=category_id,
        name=clean,
        slug=slug,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def toggle_category(db: Session, category_id: int):
    item = db.query(CatalogCategory).filter(
        CatalogCategory.id == category_id
    ).first()
    if not item:
        raise HTTPException(404, "Category not found")
    item.is_active = not item.is_active
    db.commit()
    db.refresh(item)
    return item


def toggle_subcategory(db: Session, subcategory_id: int):
    item = db.query(CatalogSubcategory).filter(
        CatalogSubcategory.id == subcategory_id
    ).first()
    if not item:
        raise HTTPException(404, "Subcategory not found")
    item.is_active = not item.is_active
    db.commit()
    db.refresh(item)
    return item
