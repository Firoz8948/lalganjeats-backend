from __future__ import annotations

"""
Create/update Chai Shai Bar's menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_chai_shai_bar_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_chai_shai_bar_menu --dry-run
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


RESTAURANT_NAME = "Chai Shai Bar"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "mocktails": "Mocktails",
    "cold-coffee": "Cold Coffee",
    "pizza": "Pizza",
    "pasta": "Pasta",
    "fries-snacks": "Fries / Snacks",
    "dosa": "Dosa",
    "uttapam": "Uttapam",
    "idli": "Idli",
    "maggie": "Maggie",
    "sizzler": "Sizzler",
    "soup": "Soup",
    "sandwich": "Grilled Sandwich",
    "burger": "Burger",
    "sweet-corn": "Sweet Corn",
    "combos": "Combos",
    "bites-site": "Bites Site",
    "chowmein": "Chowmein",
    "chinese": "Chinese",
    "rice": "Rice",
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
    item("Virgin Mojito", "Refreshing mint lime cooler", "99", "mocktails"),
    item("Spicy Mong Tango", "Spicy tangy fruit cooler", "99", "mocktails"),
    item("Blue Curacao Lemonade", "Blue citrus refreshing lemonade", "99", "mocktails"),
    item("Watermelon", "Refreshing watermelon cooler", "99", "mocktails"),
    item("Bubble Gum", "Sweet bubblegum flavored cooler", "99", "mocktails"),
    item("Green Apple", "Tangy green apple cooler", "99", "mocktails"),

    # Cold Coffee Shoffee
    item("Cold Coffee", "Chilled creamy cold coffee", "70", "cold-coffee"),
    item("Chocolate Cold Coffee", "Chocolate flavored cold coffee", "90", "cold-coffee"),
    item("Bear Cold Coffee", "Rich creamy cold coffee", "100", "cold-coffee"),
    item("Bad Wine Cold Coffee", "Unique flavored cold coffee", "100", "cold-coffee"),
    item("Brandi Cold Coffee", "Rich brandi flavored coffee", "100", "cold-coffee"),
    item("Vodka Cold Coffee", "Smooth vodka flavored coffee", "100", "cold-coffee"),
    item("Whisky Cold Coffee", "Rich whisky flavored coffee", "100", "cold-coffee"),
    item("Rum Cold Coffee", "Smooth rum flavored coffee", "100", "cold-coffee"),
    item("Irish Cold Coffee", "Creamy Irish style coffee", "100", "cold-coffee"),
    item("Caramal Cold Coffee", "Caramel flavored cold coffee", "100", "cold-coffee"),
    item("Scotch Cold Coffee", "Rich scotch flavored coffee", "100", "cold-coffee"),
    item("Hazalnut Cold Coffee", "Hazelnut flavored cold coffee", "100", "cold-coffee"),

    # Pizza Sizza
    item("Plane Pizza", "Simple classic cheese pizza", "90", "pizza"),
    item("Onion Pizza", "Fresh onion topped pizza", "100", "pizza"),
    item("Capsicum Pizza", "Fresh capsicum topped pizza", "100", "pizza"),
    item("Capsicum Onion Pizza", "Capsicum onion topped pizza", "110", "pizza"),
    item("Panner Cheese Pizza", "Paneer cheese loaded pizza", "130", "pizza"),
    item("Macsicum Hoty Pizza", "Spicy capsicum cheese pizza", "140", "pizza"),
    item("Gold Corn Pizza", "Sweet corn cheese pizza", "140", "pizza"),
    item("Tandoori Paneer Pizza", "Tandoori paneer topped pizza", "140", "pizza"),
    item("Cheese Freese Pizza", "Extra cheesy loaded pizza", "150", "pizza"),
    item("Chef Special Pizza", "Chef special loaded pizza", "160", "pizza"),
    item("Chai Shai Special Pizza", "Signature special loaded pizza", "190", "pizza"),
    item("Stuff Pizza", "Stuffed cheesy loaded pizza", "250", "pizza"),

    # Pasta Shasta
    item("Rad Sauce Pasta", "Tangy red sauce pasta", "99", "pasta"),
    item("White Sauce Pasta", "Creamy white sauce pasta", "99", "pasta"),
    item("Mix Pasta", "Mixed sauce creamy pasta", "149", "pasta"),

    # Special Dishes Wishes
    item("Franch Fries", "Crispy golden french fries", "69", "fries-snacks"),
    item("Peri Peri Fries", "Spicy peri peri fries", "79", "fries-snacks"),
    item("Masola Fries", "Spiced crispy potato fries", "79", "fries-snacks"),
    item("Cheese Fries", "Crispy fries with cheese", "89", "fries-snacks"),

    # Dosa
    item("Butter Plane Dosa", "Crispy dosa with butter", "60", "dosa"),
    item("Masala Dosa", "Crispy dosa with potato", "70", "dosa"),
    item("Butter Masala Dosa", "Butter dosa with potato", "80", "dosa"),
    item("Masur Masala Dosa", "Masur masala stuffed dosa", "90", "dosa"),
    item("Onion Masala Dosa", "Onion potato stuffed dosa", "90", "dosa"),
    item("Panner Dosa", "Paneer stuffed crispy dosa", "100", "dosa"),
    item("Panner Masala Dosa", "Paneer masala stuffed dosa", "110", "dosa"),
    item("Butter Panner Masala Dosa", "Butter paneer masala dosa", "120", "dosa"),
    item("Spring Dosa", "Spring vegetable stuffed dosa", "150", "dosa"),
    item("Sohzwane Dosa", "Spicy Schezwan stuffed dosa", "150", "dosa"),
    item("Salad Roost Dosa", "Fresh salad topped dosa", "150", "dosa"),
    item("Cron Chilli Dosa", "Corn chilli topped dosa", "160", "dosa"),
    item("Chilli Panner Dosa", "Spicy chilli paneer dosa", "170", "dosa"),
    item("Panner Salad Roost Dosa", "Paneer salad topped dosa", "190", "dosa"),
    item("Chai Shai Special Dosa", "Signature special stuffed dosa", "250", "dosa"),

    # Uttapam
    item("Onion Uttapam", "Soft uttapam with onions", "90", "uttapam"),
    item("Capsicum Uttapam", "Soft uttapam with capsicum", "90", "uttapam"),
    item("Totato Uttapam", "Soft uttapam with tomato", "90", "uttapam"),
    item("Corn Uttapam", "Soft uttapam with corn", "100", "uttapam"),
    item("Panner Uttapam", "Soft uttapam with paneer", "120", "uttapam"),

    # Idli
    item("Plane Idli", "Soft steamed rice idli", "60", "idli"),
    item("Masala Idli", "Spiced flavorful masala idli", "80", "idli"),

    # Maggie - Shaggie
    item("Plain Maggie", "Classic hot instant noodles", "40", "maggie"),
    item("Masala Maggie", "Spicy masala instant noodles", "60", "maggie"),
    item("Schezwan Maggie", "Spicy Schezwan instant noodles", "60", "maggie"),
    item("Garlic Maggie", "Garlic flavored instant noodles", "60", "maggie"),
    item("Vegetable Maggie", "Mixed vegetable instant noodles", "70", "maggie"),
    item("Cheese Butter Maggie", "Buttery cheesy instant noodles", "80", "maggie"),
    item("Peri Peri Maggie", "Spicy peri peri noodles", "80", "maggie"),
    item("Tandoori Maggie", "Smoky tandoori flavored noodles", "80", "maggie"),
    item("Tadka Maggie", "Tempered spicy instant noodles", "80", "maggie"),
    item("Corn Cheese Maggie", "Corn cheese instant noodles", "89", "maggie"),
    item("Chai Shai Bar Special", "Signature special masala noodles", "100", "maggie"),

    # Sizzler
    item("Veg Sizzler", "Hot sizzling vegetable platter", "230", "sizzler"),
    item("Schezwan Sizzler", "Spicy sizzling Schezwan platter", "250", "sizzler"),
    item("Easy Panner Sizzler", "Sizzling paneer vegetable platter", "300", "sizzler"),
    item("Chees Boll", "Crispy cheesy sizzling bites", "250", "sizzler"),
    item("Veg Chopsy", "Crispy mixed vegetable platter", "150", "sizzler"),
    item("Panner Corn Roll", "Paneer corn stuffed roll", "100", "sizzler"),
    item("Spring Roll", "Crispy vegetable spring roll", "100", "sizzler"),

    # Soup
    item("Hot/Sour Soup", "Tangy spicy vegetable soup", "50", "soup"),
    item("Manchow Soup", "Spicy Indo Chinese soup", "50", "soup"),
    item("Veg Clear Soup", "Light clear vegetable soup", "60", "soup"),
    item("Tomato Soup", "Smooth tangy tomato soup", "70", "soup"),
    item("Corn Soup", "Creamy sweet corn soup", "80", "soup"),

    # Grilled Sandwich
    item("Butter Toast", "Crispy toast with butter", "49", "sandwich"),
    item("Veg Grilled Sandwich", "Grilled vegetable cheese sandwich", "59", "sandwich"),
    item("Cheese Chatney Sandwich", "Cheesy chutney grilled sandwich", "59", "sandwich"),
    item("Panner Takatak Sandwich", "Spicy paneer grilled sandwich", "79", "sandwich"),
    item("Tikki Grilled Sandwich", "Crispy tikki grilled sandwich", "79", "sandwich"),
    item("Peri Peri Sandwich", "Spicy peri peri sandwich", "89", "sandwich"),
    item("Panjabi Tadka SAndwich", "Spicy Punjabi style sandwich", "89", "sandwich"),
    item("Chilly Panner Sandwich", "Spicy chilli paneer sandwich", "99", "sandwich"),
    item("Corn Cheese Sandwich", "Corn cheese grilled sandwich", "99", "sandwich"),
    item("Tripal Dose Sandwich", "Triple layered grilled sandwich", "100", "sandwich"),
    item("Chai Shai Special Sandwich", "Signature special grilled sandwich", "150", "sandwich"),

    # Burger Sarger
    item("Veg Burger", "Classic vegetable patty burger", "59", "burger"),
    item("Veg Cheese Burger", "Vegetable burger with cheese", "69", "burger"),
    item("Tandoori Burger", "Smoky tandoori flavored burger", "79", "burger"),
    item("Panner Burger", "Paneer patty loaded burger", "89", "burger"),
    item("Panner Cheese Burger", "Paneer burger with cheese", "99", "burger"),
    item("Panner Tikka Barger", "Paneer tikka loaded burger", "99", "burger"),

    # Sweet Corn Wor
    item("Plain", "Simple sweet corn serving", "40", "sweet-corn"),
    item("Butter Corn", "Buttery sweet corn kernels", "50", "sweet-corn"),
    item("Corn corn", "Classic seasoned sweet corn", "60", "sweet-corn"),
    item("Cheese Corn", "Cheesy sweet corn kernels", "60", "sweet-corn"),
    item("Masala Corn", "Spicy masala sweet corn", "70", "sweet-corn"),
    item("Chai Shai Bar Spl", "Signature special sweet corn", "99", "sweet-corn"),

    # Combos
    item("Chai+Coffee+Masala Maggie", "Tea coffee masala maggie combo", "60", "combos"),
    item("Chai+Coffee+Veg Sandwich", "Tea coffee sandwich combo", "60", "combos"),
    item("Cold Coffee+Veg Sandwich", "Cold coffee sandwich combo", "120", "combos"),
    item("3 Chai+To Coffee", "Three chai two coffee combo", "149", "combos"),
    item("Panner Taka Tak Sandwich+Masala Maggie", "Paneer sandwich maggie combo", "149", "combos"),
    item("2 Cold Coffee", "Two cold coffee combo", "249", "combos"),
    item("Panner Taka Tak Sandwich + Masala Maggie", "Paneer sandwich maggie combo", "249", "combos"),
    item("2 Chocolate Cold Coffee", "Two chocolate cold coffee", "349", "combos"),
    item("1 Special Pizza", "One special pizza combo", "349", "combos"),

    # Bites Site
    item("Maska Bun", "Soft bun with butter", "30", "bites-site"),
    item("Maska Bun With Cheese", "Buttery bun with cheese", "40", "bites-site"),
    item("Cheese Garlic Bread", "Garlic bread with cheese", "50", "bites-site"),

    # Chowmein
    item("Veg Chowmein", "Stir fried vegetable noodles", "70", "chowmein"),
    item("Hakka Chowmein", "Classic stir fried hakka noodles", "80", "chowmein"),
    item("Panner Chowmein", "Paneer tossed chowmein noodles", "90", "chowmein"),
    item("Schezwan Chowmein", "Spicy Schezwan style noodles", "90", "chowmein"),
    item("Chilli Garlic Chowmein", "Spicy chilli garlic noodles", "90", "chowmein"),
    item("Chees Chowmein", "Cheesy stir fried noodles", "100", "chowmein"),
    item("Singapuri Chowmein", "Spicy Singapore style noodles", "130", "chowmein"),
    item("Chai Shai Special Chowmein", "Signature special chowmein", "150", "chowmein"),

    # Chinese
    item("Veg Manchurian", "Crispy vegetable Manchurian", "80", "chinese"),
    item("Panner Manchurian", "Spicy paneer Manchurian", "100", "chinese"),
    item("Chilli Panner", "Spicy chilli paneer", "130", "chinese"),
    item("Corn Chilii", "Spicy corn chilli bites", "140", "chinese"),
    item("Crispy Corn", "Crispy seasoned sweet corn", "150", "chinese"),
    item("Veg Crispy", "Crispy mixed vegetable bites", "180", "chinese"),

    # Rice
    item("Veg Fried Rice", "Stir fried vegetable rice", "70", "rice"),
    item("Schezwan Fried Rice", "Spicy Schezwan fried rice", "90", "rice"),
    item("Panner Fried Rice", "Paneer tossed fried rice", "110", "rice"),
    item("Chilli Garlic Rice", "Spicy chilli garlic rice", "90", "rice"),
    item("Chai Shai Special Rice", "Signature special fried rice", "150", "rice"),
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
            Restaurant.name.ilike("%Chai Shai%"),
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

    menu_item = matches[0] if matches else MenuItem(restaurant_id=restaurant.id)
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