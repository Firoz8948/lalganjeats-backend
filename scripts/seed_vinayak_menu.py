from __future__ import annotations

"""
Create/update Vinayak Restaurant & Hotel's menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_vinayak_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_vinayak_menu --dry-run
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


RESTAURANT_NAME = "Vinayak Restaurant & Hotel"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "half-main-course": "Half Main Course",
    "thali": "Thali",
    "indian-main-course": "Indian Main Course",
    "chinese-starter": "Chinese Starter",
    "chinese-main-course": "Chinese Main Course",
    "rice-noodles": "Rice & Noodles",
    "bread": "Bread",
    "soup": "Special Soup",
    "raita-papad-salad": "Raita / Papad / Salad",
    "pizza": "Pizza",
    "sandwich": "Sandwich",
    "burger": "Burger",
    "breakfast": "Breakfast",
    "south-indian-dosa": "South Indian Dosa",
    "drinks": "Drinks",
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


# Names and prices are transcribed from the supplied Vinayak Restaurant & Hotel
# menu photos. Descriptions are included only where the menu itself specifies
# the contents of a thali; otherwise they are left blank.
ITEMS = [
    # Half Items (Main Course)
    item("Half Kadhai Paneer", "", "160", "half-main-course", True),
    item("Half Matar Paneer", "", "145", "half-main-course", True),
    item("Half Dal Fry", "", "110", "half-main-course", True),
    item("Half Dal Tadka", "", "130", "half-main-course", True),
    item("Plain Rice (Half)", "", "80", "half-main-course", True),
    item("Jeera Rice (Half)", "", "90", "half-main-course", True),

    # Thali
    item(
        "Thali",
        "Dal fry, matar paneer, plain rice, fresh salad and 2 tandoori roti",
        "200",
        "thali",
        True,
    ),
    item(
        "Special Thali",
        "Dal fry, kadhai paneer, mix veg, 1 butter naan, 1 missi roti, papad, jeera rice, raita, fresh salad and 1 sweet dish",
        "270",
        "thali",
        True,
    ),

    # Indian Main Course
    item("Paneer Bhurjiya", "", "240", "indian-main-course", True),
    item("Paneer Khurchan", "", "290", "indian-main-course", True),
    item("Matar Paneer", "", "230", "indian-main-course", True),
    item("Paneer Butter Masala", "", "260", "indian-main-course", True),
    item("Paneer Lababdar", "", "260", "indian-main-course", True),
    item("Kadhai Paneer", "", "260", "indian-main-course", True),
    item("Handi Paneer", "", "260", "indian-main-course", True),
    item("Paneer Do Pyaza", "", "250", "indian-main-course", True),
    item("Mix Veg", "", "200", "indian-main-course", True),
    item("Mushroom Do Pyaza", "", "250", "indian-main-course", True),
    item("Matar Mushroom", "", "240", "indian-main-course", True),
    item("Jeera Aloo", "", "180", "indian-main-course", True),
    item("Special Paneer Signature", "", "300", "indian-main-course", True),

    # Chinese Starter
    item("Chilli Paneer Dry", "", "190", "chinese-starter", True),
    item("Chilli Mushroom Dry", "", "200", "chinese-starter", True),
    item("Crispy Chilli Potato", "", "170", "chinese-starter", True),
    item("Crispy Corn", "", "180", "chinese-starter", True),
    item("Paneer 65", "", "200", "chinese-starter", True),
    item("Honey Chilli Potato", "", "180", "chinese-starter", True),
    item("Manchurian Dry", "", "180", "chinese-starter", True),
    item("French Fry", "", "110", "chinese-starter", True),
    item("Spring Roll", "", "140", "chinese-starter", True),
    item("Cheese Roll", "", "170", "chinese-starter", True),
    item("Kathi Roll", "", "160", "chinese-starter", True),

    # Chinese Main Course
    item("Chilli Paneer Gravy", "", "210", "chinese-main-course", True),
    item("Chilli Mushroom Gravy", "", "190", "chinese-main-course", True),
    item("Manchurian Gravy", "", "200", "chinese-main-course", True),

    # Rice & Noodles
    item("Paneer Rice", "", "140", "rice-noodles", True),
    item("Veg Fried Rice", "", "120", "rice-noodles", True),
    item("Schezwan Fried Rice", "", "150", "rice-noodles", True),
    item("Chilli Garlic Fried Rice", "", "160", "rice-noodles", True),
    item("Vinayak Special Fried Rice", "", "190", "rice-noodles", True),
    item("Schezwan Noodles", "", "140", "rice-noodles", True),
    item("Chilli Garlic Noodles", "", "150", "rice-noodles", True),
    item("Singapore Noodles", "", "160", "rice-noodles", True),
    item("Hakka Noodles", "", "130", "rice-noodles", True),
    item("Paneer Noodles", "", "140", "rice-noodles", True),

    # Bread
    item("Tandoori Roti", "", "10", "bread", True),
    item("Butter Roti", "", "15", "bread", True),
    item("Lachha Paratha", "", "50", "bread", True),
    item("Garlic Naan", "", "60", "bread", True),
    item("Butter Naan", "", "50", "bread", True),
    item("Missi Roti", "", "30", "bread", True),
    item("Tawa Roti", "", "10", "bread", True),
    item("Tawa Butter Roti", "", "15", "bread", True),

    # Special Soup
    item("Manchow Soup", "", "80", "soup", True),
    item("Sweet Corn Soup", "", "90", "soup", True),
    item("Tomato Soup", "", "80", "soup", True),
    item("Hakka Noodle Soup", "", "100", "soup", True),
    item("Lemon Coriander Soup", "", "110", "soup", True),

    # Raita / Papad / Salad
    item("Mix Raita", "", "90", "raita-papad-salad", True),
    item("Boondi Raita", "", "80", "raita-papad-salad", True),
    item("Fried Papad", "", "25", "raita-papad-salad", True),
    item("Masala Papad", "", "30", "raita-papad-salad", True),
    item("Roasted Papad", "", "15", "raita-papad-salad", True),
    item("Green Salad", "", "70", "raita-papad-salad", True),

    # Pizza
    item("Golden Corn Pizza", "", "200", "pizza", True),
    item("Cheese Paneer Pizza", "", "200", "pizza", True),
    item("Vinayak Special Pizza", "", "250", "pizza", True),
    item("Capsicum Onion Pizza", "", "180", "pizza", True),
    item("Chilli Paneer Pizza", "", "200", "pizza", True),

    # Sandwich
    item("Veg Sandwich", "", "80", "sandwich", True),
    item("Corn Cheese Sandwich", "", "90", "sandwich", True),
    item("Paneer Sandwich", "", "100", "sandwich", True),

    # Burger
    item("Veg Burger", "", "80", "burger", True),
    item("Cheese Burger", "", "90", "burger", True),
    item("Paneer Burger", "", "120", "burger", True),

    # Breakfast
    item("Chola Bhatura", "", "120", "breakfast", True),
    item("Pav Bhaji", "", "100", "breakfast", True),
    item("Paneer Pakoda", "", "120", "breakfast", True),
    item("Mix Pakoda", "", "110", "breakfast", True),
    item("Aloo Paratha", "", "100", "breakfast", True),
    item("Paneer Paratha", "", "120", "breakfast", True),

    # South Indian Dosa
    item("Paper Dosa", "", "110", "south-indian-dosa", True),
    item("Masala Dosa", "", "140", "south-indian-dosa", True),
    item("Paneer Dosa", "", "160", "south-indian-dosa", True),
    item("Vinayak Special Dosa", "", "200", "south-indian-dosa", True),
    item("Butter Paneer Masala Dosa", "", "180", "south-indian-dosa", True),

    # Drinks
    item("Cold Beverage Coffee", "", "100", "drinks", True),
    item("Chocolate Latte Coffee", "", "120", "drinks", True),
    item("Kulhad Lassi", "", "50", "drinks", True),
    item("Mint Mojito (Pudina)", "", "60", "drinks", True),
    item("Strawberry Mojito", "", "80", "drinks", True),
    item("Lemon Mojito", "", "80", "drinks", True),
    item("Peach Mojito", "", "90", "drinks", True),
    item("Green Apple Mojito", "", "90", "drinks", True),
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
            Restaurant.name.ilike("%Vinayak%"),
        )
        .all()
    )

    matches = [row for row in candidates if normalize_name(row.name) == target]
    if not matches:
        target_loose = normalize_name(target.replace("&", "and"))
        matches = [
            row for row in candidates
            if normalize_name(row.name.replace("&", "and")) == target_loose
            or normalize_name(row.name.replace("&", "and")) in (
                "vinayak hotel and restaurant",
                "vinayak restaurant and hotel",
                "vinayak restaurant and hotel lalganj",
            )
        ]

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
