from __future__ import annotations

"""
Create/update Freshness Point's menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_freshness_point_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_freshness_point_menu --dry-run
"""

import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.core.database import SessionLocal

# Register every mapper the same way app.main does.
from app.modules.superadmin.models import Tenant, DeliveryZone, DeliveryException  # noqa: F401
from app.modules.users.models import User, CustomerProfile, Address, CustomerSettings  # noqa: F401
from app.modules.otp.models import OTP  # noqa: F401
from app.modules.restaurants.models import (
    CatalogCategory,
    CatalogSubcategory,
    Restaurant,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
)
from app.modules.orders.models import Order, OrderItem, DeliveryProfile, DeliveryOffer  # noqa: F401
from app.modules.banners.models import HomeBannerSlide  # noqa: F401
from app.modules.payments.models import (
    PaymentSettings, RestaurantEarning, DeliveryEarning, Withdrawal, BankAccount
)  # noqa: F401
from app.modules.promocodes.models import PromoCode, PromoCodeUsage  # noqa: F401
from app.modules.admin.models import ImpersonationSession  # noqa: F401
from app.modules.admin.reports.models import ReportDelivery  # noqa: F401
from app.modules.delivery_partner.models import DeliveryPartnerDetails  # noqa: F401


RESTAURANT_NAME = "Freshness Point"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "drinks": "Drinks",
    "snacks": "Snacks",
    "burger": "Burger",
    "pizzas": "Pizzas",
    "chilli-paneer": "Chilli Paneer",
    "sandwich": "Sandwich",
    "fried-rice": "Fried Rice",
    "chowmein": "Chowmein",
    "maggi": "Maggi",
    "combos": "Combos",
}


@dataclass(frozen=True)
class Variant:
    label: str
    transfer_price: Decimal


@dataclass(frozen=True)
class MenuRow:
    name: str
    description: str
    subcategory_slug: str
    variants: tuple[Variant, ...]


def variants(*pairs: tuple[str, str]) -> tuple[Variant, ...]:
    return tuple(Variant(label, Decimal(price)) for label, price in pairs)


def single(price: str) -> tuple[Variant, ...]:
    return variants(("Regular", price))


def item(
    name: str,
    description: str,
    transfer_price: str,
    subcategory_slug: str,
) -> MenuRow:
    return MenuRow(name, description, subcategory_slug, single(transfer_price))


def item_named(
    name: str,
    description: str,
    subcategory_slug: str,
    *price_labels: tuple[str, str],
) -> MenuRow:
    return MenuRow(
        name=name,
        description=description,
        subcategory_slug=subcategory_slug,
        variants=variants(*price_labels),
    )


ITEMS = [
    # Drinks
    item("Normal Tea", "Classic refreshing hot tea", "20", "drinks"),
    item("Premium Tea", "Rich premium flavored tea", "25", "drinks"),
    item("Coffee", "Freshly brewed hot coffee", "35", "drinks"),
    item("Sikaji", "Refreshing chilled signature drink", "50", "drinks"),
    item("Iced Cold Coffee", "Chilled creamy cold coffee", "99", "drinks"),

    # Snacks
    item("Bun Makhan", "Soft bun with butter", "35", "snacks"),

    # Burger
    item("Aloo Tikki Burger", "Crispy potato patty burger", "59", "burger"),
    item("Paneer Tikki Burger", "Paneer tikki loaded burger", "69", "burger"),
    item("Cheese Burger", "Cheesy vegetable patty burger", "79", "burger"),

    # Pizzas
    item("Simple Veg Pizza", "Classic cheesy vegetable pizza", "149", "pizzas"),
    item("Combo Delight Pizza", "Loaded cheesy combo pizza", "199", "pizzas"),
    item("Tikka Tikka Pizza", "Special tikka topped pizza", "249", "pizzas"),
    item("Freshness Special Pizza", "Signature loaded special pizza", "249", "pizzas"),

    # Chilli Paneer
    item_named("Chilli Paneer", "Spicy paneer chilli preparation", "chilli-paneer",
               ("Half", "100"), ("Full", "190")),

    # Sandwich
    item("Veg Toast", "Crispy toast with vegetables", "70", "sandwich"),
    item("Veg Mayo Toast", "Creamy mayo vegetable toast", "80", "sandwich"),

    # Fried Rice
    item_named("Veg Fried Rice", "Fragrant vegetable fried rice", "fried-rice",
               ("Half", "60"), ("Full", "110")),
    item_named("Paneer Fried Rice", "Flavorful paneer fried rice", "fried-rice",
               ("Half", "70"), ("Full", "130")),
    item_named("Freshness Special Fried Rice", "Signature loaded fried rice", "fried-rice",
               ("Half", "80"), ("Full", "150")),

    # Chowmein
    item_named("Veg Chowmein", "Stir fried vegetable noodles", "chowmein",
               ("Half", "50"), ("Full", "110")),
    item_named("Paneer Chowmein", "Stir fried paneer noodles", "chowmein",
               ("Half", "60"), ("Full", "110")),
    item_named("Freshness Special Chowmein", "Signature loaded chowmein", "chowmein",
               ("Half", "70"), ("Full", "130")),

    # Maggi
    item("Normal Maggi", "Classic masala instant noodles", "70", "maggi"),
    item("Freshness Special Maggi", "Loaded signature masala Maggi", "80", "maggi"),

    # Best Combo
    item("Fried Rice + Raita", "Fried rice served with raita", "119", "combos"),
    item("Fried Rice + Chilli Paneer + Tea",
         "Fried rice with chilli paneer", "149", "combos"),
]


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def normalize_name(value: str) -> str:
    return " ".join((value or "").casefold().split())


def find_restaurant(db) -> Restaurant:
    tenant = db.query(Tenant).filter(Tenant.slug == TENANT_SLUG).one_or_none()
    if tenant is None:
        raise RuntimeError(f"Tenant with slug '{TENANT_SLUG}' was not found.")

    target = normalize_name(RESTAURANT_NAME)
    candidates = (
        db.query(Restaurant)
        .filter(
            Restaurant.tenant_id == tenant.id,
            Restaurant.name.ilike("%Freshness Point%"),
        )
        .all()
    )

    matches = [row for row in candidates if normalize_name(row.name) == target]
    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple restaurants matching '{RESTAURANT_NAME}' exist in tenant "
            f"'{TENANT_SLUG}'. Aborting to avoid changing the wrong restaurant."
        )

    names = ", ".join(
        f"#{row.id} {row.name!r}" for row in candidates
    ) or "none"

    raise RuntimeError(
        f"Exact restaurant '{RESTAURANT_NAME}' was not found in tenant "
        f"'{TENANT_SLUG}'. Similar matches: {names}"
    )


def load_subcategories(
    db, restaurant: Restaurant
) -> dict[str, CatalogSubcategory]:
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
    next_order = max(
        (row.sort_order or 0 for row in rows),
        default=0,
    ) + 1

    for slug in missing:
        subcategory = CatalogSubcategory(
            category_id=restaurant_category.id,
            name=SUBCATEGORIES[slug],
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
    row: MenuRow,
    subcategory: CatalogSubcategory,
) -> str:
    category = get_or_create_menu_category(
        db,
        restaurant.id,
        subcategory,
    )

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

    menu_item = (
        matches[0]
        if matches
        else MenuItem(restaurant_id=restaurant.id)
    )
    action = "updated" if matches else "created"

    first = row.variants[0]
    display_price = money(first.transfer_price * DISPLAY_MARKUP)
    mrp = money(first.transfer_price * MRP_MARKUP)

    menu_item.category_id = category.id
    menu_item.business_subcategory_id = subcategory.id
    menu_item.name = row.name
    menu_item.description = row.description
    menu_item.actual_price = money(first.transfer_price)
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

    existing_variants = (
        db.query(MenuItemVariant)
        .filter(MenuItemVariant.menu_item_id == menu_item.id)
        .all()
    )

    by_label = {
        (v.label or "").casefold(): v
        for v in existing_variants
    }

    intended_labels = set()

    for sort_order, variant_data in enumerate(row.variants):
        label = variant_data.label
        transfer = variant_data.transfer_price
        variant_display = money(transfer * DISPLAY_MARKUP)
        variant_mrp = money(transfer * MRP_MARKUP)

        variant = by_label.get(label.casefold())

        if variant is None:
            variant = MenuItemVariant(
                menu_item_id=menu_item.id,
                label=label,
            )
            db.add(variant)

        variant.actual_price = money(transfer)
        variant.price = variant_display
        variant.original_price = variant_mrp
        variant.sort_order = sort_order
        variant.is_available = True
        variant.is_deleted = False

        intended_labels.add(label.casefold())

        print(
            f"{action:7} {row.name:<48} [{label:<8}] "
            f"transfer=₹{transfer:.2f} "
            f"display=₹{variant_display:.2f} "
            f"MRP=₹{variant_mrp:.2f} "
            f"[{subcategory.name}]"
        )

    # Retire stale variants so old sizes/options are not still shown.
    for variant in existing_variants:
        if (variant.label or "").casefold() not in intended_labels:
            variant.is_available = False
            variant.is_deleted = True

    return action


def seed(dry_run: bool = False) -> None:
    if not ITEMS:
        raise RuntimeError("No menu items defined.")

    db = SessionLocal()

    try:
        restaurant = find_restaurant(db)
        subcategories = load_subcategories(db, restaurant)

        print(
            f"Restaurant: #{restaurant.id} {restaurant.name} "
            f"(tenant_id={restaurant.tenant_id})"
        )

        print(
            f"Pricing: display = transfer + 30%; "
            f"MRP = transfer + 39%; items={len(ITEMS)}"
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

            if action == "created":
                created += 1
            else:
                updated += 1

        if dry_run:
            db.rollback()
            print(
                f"DRY RUN: rolled back "
                f"{created} create(s), {updated} update(s)."
            )
        else:
            db.commit()
            print(
                f"Done: {created} item(s) created, "
                f"{updated} item(s) updated."
            )

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