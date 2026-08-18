from __future__ import annotations

"""
Create/update Hot N Cool Cups' menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_hot_cool_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_hot_cool_menu --dry-run
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


RESTAURANT_NAME = "Hot N Cool Cups"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")




SUBCATEGORIES = {
    "mocktails": "Mocktails",
    "shakes": "Shakes",
    "cold-coffee": "Cold Coffee",
    "starters": "Starters",
    "noodles": "Noodles",
    "rice": "Rice",
    "sandwiches": "Sandwiches",
    "pizza": "Pizza",
    "burger": "Burger",
    "corn": "Corn Special",
    "pasta": "Pasta",
    "fries": "Fries",
    "maggi": "Maggi",
    "waffles": "Waffles",
    "combo-meals": "Combo Meals",
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
    # Mocktails
    item("Virgin Mojito", "Refreshing mint lime mocktail", "50", "mocktails"),
    item("Kala Khatta", "Tangy kala khatta mocktail", "50", "mocktails"),
    item("Watermelon", "Refreshing watermelon mocktail", "50", "mocktails"),
    item("Blue Curacao", "Citrusy blue curacao mocktail", "50", "mocktails"),
    item("Pineapple", "Tropical pineapple mocktail", "50", "mocktails"),
    item("Green Mint", "Refreshing green mint mocktail", "50", "mocktails"),

    # Shakes
    item("Vanilla Shake", "Creamy classic vanilla shake", "60", "shakes"),
    item("Mango Shake", "Creamy fruity mango shake", "60", "shakes"),
    item("Strawberry Shake", "Creamy strawberry flavored shake", "80", "shakes"),
    item("Chocolate Shake", "Rich creamy chocolate shake", "80", "shakes"),
    item("Blue Curacao Shake", "Creamy citrus blue shake", "80", "shakes"),
    item("Kesar Pista Shake", "Creamy saffron pistachio shake", "80", "shakes"),
    item("Oreo Shake", "Creamy cookies and cream shake", "90", "shakes"),
    item("KitKat Shake", "Chocolate wafer blended shake", "100", "shakes"),
    item("Kiwi Shake", "Creamy refreshing kiwi shake", "100", "shakes"),

    # Cold Coffee
    item("Cold Coffee", "Chilled creamy coffee blend", "90", "cold-coffee"),
    item("Mocha Coffee", "Chocolate flavored chilled coffee", "90", "cold-coffee"),
    item("Premium Coffee", "Rich premium chilled coffee", "120", "cold-coffee"),

    # Starters / Snacks
    item_named("Chilli Potato", "Crispy spicy chilli potatoes", "starters", ("Half", "120"), ("Full", "140")),
    item_named("Chilli Paneer", "Spicy paneer with peppers", "starters", ("Half", "160"), ("Full", "180")),
    item_named("Manchurian", "Crispy vegetable Manchurian bites", "starters", ("Half", "140"), ("Full", "160")),
    item_named("Paneer Manchurian", "Crispy paneer Manchurian bites", "starters", ("Half", "180"), ("Full", "200")),

    # Noodles
    item("Veg Noodles", "Stir fried vegetable noodles", "90", "noodles"),
    item("Paneer Noodles", "Stir fried paneer noodles", "120", "noodles"),
    item("Schezwan Noodles", "Spicy Schezwan style noodles", "110", "noodles"),
    item("Garlic Noodles", "Garlic flavored stir fried noodles", "130", "noodles"),
    item("Hakka Noodles", "Classic Indo Chinese noodles", "150", "noodles"),

    # Rice
    item("Veg Rice", "Flavorful mixed vegetable rice", "90", "rice"),
    item("Paneer Rice", "Flavorful rice with paneer", "120", "rice"),
    item("Manchurian Rice", "Rice with Manchurian flavors", "140", "rice"),
    item("Schezwan Rice", "Spicy Schezwan vegetable rice", "160", "rice"),

    # Sandwiches
    item("Veg Grilled Sandwich", "Grilled sandwich with vegetables", "55", "sandwiches"),
    item("Paneer Grilled Sandwich", "Grilled sandwich with paneer", "70", "sandwiches"),
    item("Special Sandwich", "Loaded signature grilled sandwich", "90", "sandwiches"),

    # Pizza
    item_named("Plain Cheese Pizza", "Classic cheesy pizza", "pizza", ("Regular", "100"), ("Large", "130")),
    item_named("Onion Pizza", "Cheesy pizza with onion", "pizza", ("Regular", "110"), ("Large", "140")),
    item_named("Veg Pizza", "Cheesy pizza with vegetables", "pizza", ("Regular", "130"), ("Large", "160")),
    item_named("Paneer Capsicum Pizza", "Pizza with paneer and capsicum", "pizza", ("Regular", "160"), ("Large", "190")),
    item_named("Cheese Corn Pizza", "Cheesy pizza with sweet corn", "pizza", ("Regular", "160"), ("Large", "190")),
    item_named("Special Pizza", "Loaded signature special pizza", "pizza", ("Regular", "200"), ("Large", "230")),

    # Burger
    item("Veg Burger", "Classic vegetable burger", "60", "burger"),
    item("Paneer Burger", "Loaded paneer vegetable burger", "75", "burger"),
    item("Special Tandoori Burger", "Smoky tandoori style burger", "90", "burger"),

    # Corn Special
    item("Masala Corn", "Spicy seasoned sweet corn", "80", "corn"),
    item("Special Corn", "Loaded special sweet corn", "100", "corn"),
    item("Crispy Corn", "Crispy seasoned sweet corn", "120", "corn"),

    # Pasta
    item("Red Sauce Pasta", "Pasta in tangy red sauce", "100", "pasta"),
    item("White Sauce Pasta", "Creamy pasta in white sauce", "100", "pasta"),
    item("Mix Sauce Pasta", "Pasta in mixed creamy sauce", "100", "pasta"),

    # Fries
    item("French Fries", "Crispy golden potato fries", "60", "fries"),
    item("Peri Peri Fries", "Crispy fries with peri peri", "80", "fries"),

    # Maggi
    item("Plain Maggi", "Classic masala instant noodles", "60", "maggi"),
    item("Veg Maggi", "Instant noodles with vegetables", "75", "maggi"),
    item("Paneer Maggi", "Instant noodles with paneer", "90", "maggi"),

    # Waffles
    item("Freshness Waffle", "Crispy waffle with sweet topping", "100", "waffles"),
    item("Chocolate Waffle", "Chocolate topped crispy waffle", "120", "waffles"),

    # Combo Meals
    item("Chilli Paneer + Fried Rice/Noodles", "Chilli paneer with rice noodles", "150", "combo-meals"),
    item("Manchurian + Fried Rice/Noodles", "Manchurian with fried rice noodles", "130", "combo-meals"),
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
            Restaurant.name.ilike("%Hot%Cool%"),
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