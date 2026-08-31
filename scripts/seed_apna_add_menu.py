from __future__ import annotations

"""
Create/update Apna Adda's menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_apna_add_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_apna_add_menu --dry-run
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


RESTAURANT_NAME = "Apna Adda"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "hot-coffee": "Hot Coffee",
    "cold-coffee": "Cold Coffee",
    "tea": "Tea",
    "shake": "Shake",
    "mocktail": "Mocktail",
    "pasta": "Pasta",
    "pav-bhaji": "Pav Bhaji",
    "cold-drinks": "Cold Drinks",
    "sandwich": "Sandwich",
    "special-dish": "Special Dish",
    "dosa": "Dosa",
    "manchurian": "Manchurian",
    "pizza": "Pizza",
    "maggi": "Maggi",
    "chowmein": "Chowmein",
    "chilli-paneer": "Chilli Paneer",
    "fried-rice": "Fried Rice",
    "burger": "Burger",
    "corn": "Corn",
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
    is_veg: bool


def variants(*pairs: tuple[str, str]) -> tuple[Variant, ...]:
    return tuple(Variant(label, Decimal(price)) for label, price in pairs)


def single(price: str) -> tuple[Variant, ...]:
    return variants(("Regular", price))


def item(
    name: str,
    description: str,
    transfer_price: str,
    subcategory_slug: str,
    is_veg: bool,
) -> MenuRow:
    return MenuRow(
        name=name,
        description=description,
        subcategory_slug=subcategory_slug,
        variants=single(transfer_price),
        is_veg=is_veg,
    )


def item_named(
    name: str,
    description: str,
    subcategory_slug: str,
    is_veg: bool,
    *price_labels: tuple[str, str],
) -> MenuRow:
    return MenuRow(
        name=name,
        description=description,
        subcategory_slug=subcategory_slug,
        variants=variants(*price_labels),
        is_veg=is_veg,
    )


# Names and prices are transcribed from the supplied Apna Adda menu photos.
# Descriptions are left blank because the menu photos do not provide descriptions.
ITEMS = [
    # Hot Coffee
    item("Hot Coffee", "", "15", "hot-coffee", True),
    item("Chocolate Coffee", "", "20", "hot-coffee", True),
    item("Strong Coffee", "", "20", "hot-coffee", True),
    item("Milk Coffee", "", "25", "hot-coffee", True),

    # Cold Coffee
    item("Cold Coffee", "", "70", "cold-coffee", True),
    item("Cold Coffee with Ice Cream", "", "85", "cold-coffee", True),
    item("Chocolate Cold Coffee", "", "80", "cold-coffee", True),
    item("Chocolate Cold Coffee with Ice Cream", "", "90", "cold-coffee", True),
    item("Apna Adda Special Cold Coffee", "", "120", "cold-coffee", True),

    # Tea
    item("Normal Tea", "", "10", "tea", True),
    item("Chocolate Tea", "", "15", "tea", True),
    item("Vanilla Tea", "", "15", "tea", True),
    item("Rose Tea", "", "15", "tea", True),
    item("Ginger, Cardamom Tea", "", "15", "tea", True),
    item("Saffron Cardamom Tea", "", "15", "tea", True),
    item("Java Malai Tea", "", "15", "tea", True),
    item("Rabdi Tea", "", "15", "tea", True),

    # Mocktail
    item("Virgin Mojito", "", "90", "mocktail", True),
    item("Spicy Mango Tango", "", "100", "mocktail", True),
    item("Blue Curacao", "", "100", "mocktail", True),
    item("Watermelon", "", "115", "mocktail", True),

    # Pasta
    item("Red Sauce Pasta", "", "90", "pasta", True),
    item("White Sauce Pasta", "", "90", "pasta", True),
    item("Mix Pasta", "", "90", "pasta", True),
    item("Masala Pasta", "", "90", "pasta", True),

    # Pav Bhaji
    item("Cheese Pav Bhaji", "", "80", "pav-bhaji", True),
    item("Apna Adda Special Pav Bhaji", "", "100", "pav-bhaji", True),
    item("Rusk Bun", "", "30", "pav-bhaji", True),
    item("Garlic Bread", "", "65", "pav-bhaji", True),

    # Cold Drinks
    item("Cold Drink", "", "70", "cold-drinks", True),
    item("Cold Drink with Ice Cream", "", "85", "cold-drinks", True),

    # Shake
    item("Vanilla Shake", "", "80", "shake", True),
    item("Butter Scotch Shake", "", "80", "shake", True),
    item("Coffee Shake", "", "80", "shake", True),
    item("Litchi Shake", "", "80", "shake", True),
    item("Mango Shake", "", "80", "shake", True),
    item("Oreo Shake", "", "90", "shake", True),
    item("Kitkat Shake", "", "90", "shake", True),
    item("Cadbury Shake", "", "90", "shake", True),

    # Sandwich
    item("Butter Toast", "", "39", "sandwich", True),
    item("Veg Grilled Sandwich", "", "59", "sandwich", True),
    item("Paneer Sandwich", "", "69", "sandwich", True),
    item("Tikki Sandwich", "", "79", "sandwich", True),
    item("Punjabi Tadka Sandwich", "", "79", "sandwich", True),
    item("Pizza Sandwich", "", "69", "sandwich", True),
    item("Cheese Corn Sandwich", "", "89", "sandwich", True),
    item("Apna Adda Special Sandwich", "", "99", "sandwich", True),

    # Special Dish
    item("French Fry", "", "65", "special-dish", True),
    item("Peri Peri Fry", "", "65", "special-dish", True),
    item("Masala Fry", "", "75", "special-dish", True),
    item("Cheese Fry", "", "80", "special-dish", True),
    item("Apna Adda Special Fry", "", "99", "special-dish", True),

    # Dosa
    item("Plain Dosa", "", "49", "dosa", True),
    item("Masala Dosa", "", "59", "dosa", True),
    item("Butter Dosa", "", "79", "dosa", True),
    item("Butter Cheese Dosa", "", "89", "dosa", True),
    item("Apna Adda Special Dosa", "", "120", "dosa", True),

    # Manchurian
    item_named(
        "Veg Manchurian", "", "manchurian", True,
        ("Half", "70"), ("Full", "130"),
    ),
    item_named(
        "Paneer Manchurian", "", "manchurian", True,
        ("Half", "60"), ("Full", "120"),
    ),

    # Pizza
    item("Plain Cheese Pizza", "", "90", "pizza", True),
    item("Capsicum Onion Pizza", "", "110", "pizza", True),
    item("Onion Pizza", "", "100", "pizza", True),
    item("Tandoori Paneer Pizza", "", "130", "pizza", True),
    item("Veggie Paneer Pizza", "", "130", "pizza", True),
    item("Corn Pizza", "", "130", "pizza", True),
    item("Golden Corn Pizza", "", "130", "pizza", True),
    item("Capsicum Hot Pizza", "", "140", "pizza", True),
    item("Apna Adda Special Pizza", "", "180", "pizza", True),

    # Maggi
    item("Plain Maggi", "", "40", "maggi", True),
    item("Double Masala Maggi", "", "49", "maggi", True),
    item("Schezwan Maggi", "", "59", "maggi", True),
    item("Vegetable Maggi", "", "59", "maggi", True),
    item("Cheese Butter Maggi", "", "69", "maggi", True),
    item("Corn Cheese Maggi", "", "69", "maggi", True),
    item("Cheese Garlic Maggi", "", "69", "maggi", True),
    item("Apna Adda Special Maggi", "", "99", "maggi", True),

    # Chowmein
    item("Normal Chowmein", "", "60", "chowmein", True),
    item("Schezwan Chowmein", "", "70", "chowmein", True),
    item("Manchurian Chowmein", "", "70", "chowmein", True),
    item("Paneer Chowmein", "", "80", "chowmein", True),
    item("Apna Adda Special Chowmein", "", "100", "chowmein", True),

    # Chilli Paneer
    item("Chilli Potato", "", "60", "chilli-paneer", True),
    item("Chilli Paneer", "", "80", "chilli-paneer", True),
    item("Paneer Pakoda", "", "80", "chilli-paneer", True),

    # Fried Rice
    item_named(
        "Veg Fried Rice", "", "fried-rice", True,
        ("Half", "50"), ("Full", "90"),
    ),
    item_named(
        "Veg Schezwan Rice", "", "fried-rice", True,
        ("Half", "60"), ("Full", "110"),
    ),
    item_named(
        "Veg Manchurian Rice", "", "fried-rice", True,
        ("Half", "65"), ("Full", "120"),
    ),
    item_named(
        "Veg Paneer Rice", "", "fried-rice", True,
        ("Half", "70"), ("Full", "130"),
    ),
    item_named(
        "Veg Triple Rice", "", "fried-rice", True,
        ("Half", "80"), ("Full", "150"),
    ),
    item_named(
        "Apna Adda Special Rice", "", "fried-rice", True,
        ("Half", "100"), ("Full", "180"),
    ),

    # Burger
    item("Veg Burger", "", "50", "burger", True),
    item("Veg Cheese Burger", "", "70", "burger", True),
    item("Tandoori Burger", "", "80", "burger", True),
    item("Paneer Tikka Burger", "", "100", "burger", True),

    # Corn
    item("Plain Corn", "", "45", "corn", True),
    item("Butter Corn", "", "55", "corn", True),
    item("Cheese Corn", "", "65", "corn", True),
    item("Crispy Corn", "", "140", "corn", True),
    item("Apna Adda Special Corn", "", "140", "corn", True),
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
            Restaurant.name.ilike("%Apna%Adda%"),
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
    menu_item.is_veg = row.is_veg
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
