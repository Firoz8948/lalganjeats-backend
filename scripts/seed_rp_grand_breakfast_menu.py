"""
Create/update Hotel RP Grand & Restaurants' 21-item breakfast menu.

The printed menu price is treated as the seller transfer price:
  display price = seller transfer + 30%
  MRP           = seller transfer + 35%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_rp_grand_breakfast_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_rp_grand_breakfast_menu --dry-run
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.core.database import SessionLocal

# Register every mapper the same way app.main does, or SQLAlchemy fails on
# unresolved relationship strings (User, DeliveryPartnerDetails, etc.).
from app.modules.superadmin.models import (  # noqa: F401
    Tenant,
    DeliveryZone,
    DeliveryException,
)
from app.modules.users.models import (  # noqa: F401
    User,
    CustomerProfile,
    Address,
    CustomerSettings,
)
from app.modules.otp.models import OTP  # noqa: F401
from app.modules.restaurants.models import (
    CatalogCategory,
    CatalogSubcategory,
    Restaurant,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
)
from app.modules.orders.models import (  # noqa: F401
    Order,
    OrderItem,
    DeliveryProfile,
    DeliveryOffer,
)
from app.modules.banners.models import HomeBannerSlide  # noqa: F401
from app.modules.payments.models import (  # noqa: F401
    PaymentSettings,
    RestaurantEarning,
    DeliveryEarning,
    Withdrawal,
    BankAccount,
)
from app.modules.promocodes.models import PromoCode, PromoCodeUsage  # noqa: F401
from app.modules.admin.models import ImpersonationSession  # noqa: F401
from app.modules.admin.reports.models import ReportDelivery  # noqa: F401
from app.modules.delivery_partner.models import DeliveryPartnerDetails  # noqa: F401


RESTAURANT_NAME = "Hotel RP Grand & Restaurants"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.35")
MONEY = Decimal("0.01")
SUBCATEGORY_NAMES = {
    "paratha": "Paratha",
    "north-indian": "North Indian",
    "pav-bhaji": "Pav Bhaji",
    "dosa": "Dosa",
    "uttapam": "Uttapam",
    "healthy-food": "Healthy Food",
    "south-indian": "South Indian",
    "beverages": "Beverages",
}


@dataclass(frozen=True)
class BreakfastItem:
    name: str
    description: str
    transfer_price: Decimal
    subcategory_slug: str


def item(
    name: str,
    description: str,
    transfer_price: str,
    subcategory_slug: str,
) -> BreakfastItem:
    return BreakfastItem(
        name=name,
        description=description,
        transfer_price=Decimal(transfer_price),
        subcategory_slug=subcategory_slug,
    )


ITEMS = [
    item("Aloo Paratha", "Soft potato-stuffed flavorful Indian flatbread", "149", "paratha"),
    item("Mix Paratha", "Flavorful flatbread stuffed with mixed vegetables", "159", "paratha"),
    item("Gobhi Paratha", "Spiced cauliflower-stuffed Indian flatbread", "169", "paratha"),
    item("Paneer Paratha", "Soft paneer-stuffed flavorful flatbread", "179", "paratha"),
    item("Puri Sabzi", "Fluffy puris with spiced vegetable curry", "179", "north-indian"),
    item("Chhola Bhatura", "Spicy chickpeas with fluffy bhatura", "179", "north-indian"),
    item("Pav Bhaji", "Spiced mashed vegetables with buttery pav", "159", "pav-bhaji"),
    item("Paper Dosa", "Thin crispy South Indian rice crepe", "129", "dosa"),
    item("Masala Dosa", "Crispy dosa with spiced potato filling", "159", "dosa"),
    item("Paneer Dosa", "Crispy dosa with flavorful paneer filling", "179", "dosa"),
    item("Cheesy Masala Dosa", "Cheesy dosa with spicy potato filling", "199", "dosa"),
    item("Rawa Plain Dosa", "Crispy semolina dosa with classic flavors", "179", "dosa"),
    item("Rawa Masala Dosa", "Crispy semolina dosa with potato filling", "199", "dosa"),
    item("Rawa Paneer Dosa", "Semolina dosa with delicious paneer filling", "209", "dosa"),
    item("Onion Uttapam", "Soft uttapam topped with fresh onions", "149", "uttapam"),
    item("Mix Veg Uttapam", "Soft uttapam loaded with mixed vegetables", "179", "uttapam"),
    item("Paneer Uttapam", "Soft uttapam topped with flavorful paneer", "189", "uttapam"),
    item("Poha", "Light flattened rice with aromatic spices", "119", "healthy-food"),
    item("Vada Sambhar", "Crispy lentil vada with flavorful sambhar", "139", "south-indian"),
    item("Butter Milk", "Refreshing chilled spiced buttermilk", "89", "beverages"),
    item(
        "Masala Butter Milk",
        "Chilled buttermilk blended with aromatic spices",
        "109",
        "beverages",
    ),
]


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def find_restaurant(db) -> Restaurant:
    tenant = db.query(Tenant).filter(Tenant.slug == TENANT_SLUG).one_or_none()
    if tenant is None:
        raise RuntimeError(f"Tenant with slug '{TENANT_SLUG}' was not found.")

    exact = (
        db.query(Restaurant)
        .filter(
            Restaurant.tenant_id == tenant.id,
            func.lower(Restaurant.name) == RESTAURANT_NAME.lower(),
        )
        .all()
    )
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise RuntimeError(
            f"Multiple restaurants named '{RESTAURANT_NAME}' exist in tenant "
            f"'{TENANT_SLUG}'. Aborting to avoid changing the wrong restaurant."
        )

    candidates = (
        db.query(Restaurant)
        .filter(
            Restaurant.tenant_id == tenant.id,
            Restaurant.name.ilike("%RP Grand%"),
        )
        .all()
    )
    names = ", ".join(f"#{row.id} {row.name!r}" for row in candidates) or "none"
    raise RuntimeError(
        f"Exact restaurant '{RESTAURANT_NAME}' was not found in tenant "
        f"'{TENANT_SLUG}'. Similar matches: {names}"
    )


def load_subcategories(db, restaurant: Restaurant) -> dict[str, CatalogSubcategory]:
    restaurant_category = (
        db.query(CatalogCategory)
        .filter(CatalogCategory.slug == "restaurant")
        .one_or_none()
    )
    if restaurant_category is None:
        restaurant_category = CatalogCategory(
            name="Restaurant",
            slug="restaurant",
            is_active=True,
            sort_order=1,
        )
        db.add(restaurant_category)
        db.flush()
    else:
        restaurant_category.is_active = True

    if restaurant.business_category_id is None:
        restaurant.business_category_id = restaurant_category.id
    elif restaurant.business_category_id != restaurant_category.id:
        raise RuntimeError(
            f"Restaurant #{restaurant.id} is not assigned to the Restaurant catalog category."
        )

    required = {row.subcategory_slug for row in ITEMS}
    rows = (
        db.query(CatalogSubcategory)
        .filter(
            CatalogSubcategory.category_id == restaurant_category.id,
            CatalogSubcategory.slug.in_(required),
        )
        .all()
    )
    by_slug = {row.slug: row for row in rows}
    missing = sorted(required - by_slug.keys())
    next_order = max((row.sort_order or 0 for row in rows), default=0) + 1
    for slug in missing:
        subcategory = CatalogSubcategory(
            category_id=restaurant_category.id,
            name=SUBCATEGORY_NAMES[slug],
            slug=slug,
            sort_order=next_order,
            is_active=True,
        )
        next_order += 1
        db.add(subcategory)
        by_slug[slug] = subcategory
    for subcategory in by_slug.values():
        subcategory.is_active = True
    if missing:
        db.flush()
    return by_slug


def get_or_create_menu_category(
    db,
    restaurant_id: int,
    subcategory: CatalogSubcategory,
) -> MenuCategory:
    category = (
        db.query(MenuCategory)
        .filter(
            MenuCategory.restaurant_id == restaurant_id,
            func.lower(MenuCategory.name) == subcategory.name.lower(),
        )
        .one_or_none()
    )
    if category is None:
        category = MenuCategory(
            restaurant_id=restaurant_id,
            name=subcategory.name,
            is_active=True,
        )
        db.add(category)
        db.flush()
    else:
        category.is_active = True
    return category


def upsert_item(
    db,
    restaurant: Restaurant,
    row: BreakfastItem,
    subcategory: CatalogSubcategory,
) -> str:
    category = get_or_create_menu_category(db, restaurant.id, subcategory)
    matches = (
        db.query(MenuItem)
        .filter(
            MenuItem.restaurant_id == restaurant.id,
            func.lower(MenuItem.name) == row.name.lower(),
        )
        .all()
    )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple menu items named {row.name!r} exist for restaurant "
            f"#{restaurant.id}. Aborting instead of guessing."
        )

    display_price = money(row.transfer_price * DISPLAY_MARKUP)
    mrp = money(row.transfer_price * MRP_MARKUP)
    menu_item = matches[0] if matches else MenuItem(restaurant_id=restaurant.id)
    action = "updated" if matches else "created"

    menu_item.category_id = category.id
    menu_item.business_subcategory_id = subcategory.id
    menu_item.name = row.name
    menu_item.description = row.description
    menu_item.actual_price = money(row.transfer_price)
    menu_item.price = display_price
    menu_item.original_price = mrp
    menu_item.is_veg = True
    menu_item.is_available = True
    menu_item.is_deleted = False
    menu_item.deleted_at = None
    if not matches:
        menu_item.is_bestseller = False
        db.add(menu_item)
        db.flush()

    variants = (
        db.query(MenuItemVariant)
        .filter(MenuItemVariant.menu_item_id == menu_item.id)
        .all()
    )
    regular = next((v for v in variants if v.label.casefold() == "regular"), None)
    if regular is None:
        regular = MenuItemVariant(menu_item_id=menu_item.id, label="Regular")
        db.add(regular)
    regular.actual_price = money(row.transfer_price)
    regular.price = display_price
    regular.original_price = mrp
    regular.sort_order = 0
    regular.is_available = True
    regular.is_deleted = False

    # These seed entries are single-price products. Retire any stale custom
    # variants so the customer sees only the intended Regular price.
    for variant in variants:
        if variant is not regular:
            variant.is_available = False
            variant.is_deleted = True

    print(
        f"{action:7} {row.name:<20} "
        f"transfer=₹{row.transfer_price:.2f} "
        f"display=₹{display_price:.2f} MRP=₹{mrp:.2f} "
        f"[{subcategory.name}]"
    )
    return action


def seed(dry_run: bool = False) -> None:
    if len(ITEMS) != 21:
        raise RuntimeError(f"Expected 21 menu items, found {len(ITEMS)}.")

    db = SessionLocal()
    try:
        restaurant = find_restaurant(db)
        subcategories = load_subcategories(db, restaurant)
        print(
            f"Restaurant: #{restaurant.id} {restaurant.name} "
            f"(tenant_id={restaurant.tenant_id})"
        )

        created = 0
        updated = 0
        for row in ITEMS:
            action = upsert_item(
                db,
                restaurant,
                row,
                subcategories[row.subcategory_slug],
            )
            created += action == "created"
            updated += action == "updated"

        if dry_run:
            db.rollback()
            print(f"DRY RUN: rolled back {created} create(s), {updated} update(s).")
        else:
            db.commit()
            print(f"Done: {created} item(s) created, {updated} item(s) updated.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print changes, then roll them back.",
    )
    args = parser.parse_args()
    seed(dry_run=args.dry_run)
