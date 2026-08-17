from __future__ import annotations

"""
Create/update Shyam Sawariya Sweets' menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_sawariya_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_sawariya_menu --dry-run
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


RESTAURANT_NAME = "Shyam Sawariya Sweets"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "chinese": "Chinese",
    "pizza": "Pizza",
    "main-course": "Main Course",
    "roti": "Roti",
    "paratha": "Paratha",
    "dal": "Dal",
    "rice": "Rice",
    "salad": "Salad",
    "papad": "Papad",
    "raita": "Raita",
    "snacks": "Snacks",
    "soup": "Soup",
    "south-indian": "South Indian",
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
    # Chinese
    item("Veg Manchurian", "Crispy vegetable Manchurian balls", "160", "chinese"),
    item("Paneer", "Soft paneer Chinese preparation", "170", "chinese"),
    item_named("Chilli Paneer (Dry)", "Crispy paneer with chilli", "chinese",
                ("Half", "90"), ("Full", "180")),
    item("Chilli Paneer Gravy", "Spicy paneer in gravy", "180", "chinese"),
    item_named("Veg Fried Rice", "Fragrant fried rice vegetables", "chinese",
                ("Half", "90"), ("Full", "150")),
    item_named("Paneer Fried Rice", "Flavorful paneer Chinese rice", "chinese",
                ("Half", "100"), ("Full", "160")),
    item_named("Hakka Noodles", "Classic stir fried Hakka noodles", "chinese",
                ("Half", "100"), ("Full", "170")),
    item("Chilli Garlic Chowmein", "Spicy garlic tossed chowmein", "160", "chinese"),
    item_named("Singapore Chowmein", "Spicy Singapore style noodles", "chinese",
                ("Half", "100"), ("Full", "160")),
    item_named("Mushroom Chowmein", "Mushroom tossed chowmein noodles", "chinese",
                ("Half", "100"), ("Full", "170")),

    # Pizza
    item("Onion Pizza", "Cheesy pizza topped with onion", "220", "pizza"),
    item("Paneer Pizza", "Cheesy pizza with paneer", "280", "pizza"),
    item("Paneer Double Cheese Pizza", "Paneer pizza with extra cheese", "300", "pizza"),
    item("Special Sawariya Pizza", "Loaded signature Sawariya pizza", "320", "pizza"),

    # Main Course
    item("Matar Paneer", "Paneer cooked with green peas", "210", "main-course"),
    item("Shahi Paneer", "Rich creamy royal paneer curry", "220", "main-course"),
    item("Kadhai Paneer", "Spiced paneer in kadhai gravy", "220", "main-course"),
    item("Paneer Do Pyaza", "Paneer cooked with onions", "220", "main-course"),
    item("Mix Veg", "Mixed vegetables in flavorful gravy", "210", "main-course"),
    item("Mushroom Matar", "Mushroom cooked with green peas", "230", "main-course"),
    item("Mushroom Masala", "Spiced mushroom masala curry", "210", "main-course"),
    item("Aloo Jeera", "Potatoes tempered with cumin", "140", "main-course"),
    item("Palak Paneer", "Paneer cooked in spinach gravy", "240", "main-course"),

    # Roti
    item("Tandoori Roti", "Crispy tandoor baked Indian bread", "20", "roti"),
    item("Butter Tandoori Roti", "Buttery tandoor baked Indian bread", "25", "roti"),
    item("Butter Naan", "Soft naan topped with butter", "45", "roti"),
    item("Plain Naan", "Soft classic tandoori naan", "40", "roti"),
    item("Missi Roti", "Spiced gram flour Indian bread", "50", "roti"),
    item("Tawa Roti", "Soft freshly cooked tawa roti", "15", "roti"),
    item("Tawa Tandoori Roti", "Tawa cooked tandoori style roti", "20", "roti"),

    # Paratha
    item("Aloo Paratha", "Potato stuffed Indian flatbread", "90", "paratha"),
    item("Mix Paratha", "Mixed vegetable stuffed flatbread", "130", "paratha"),
    item("Paneer Paratha", "Paneer stuffed Indian flatbread", "140", "paratha"),
    item("Laccha Paratha", "Layered crispy Indian flatbread", "110", "paratha"),
    item("Gobhi Paratha", "Cauliflower stuffed Indian flatbread", "110", "paratha"),

    # Dal
    item("Daal Fry", "Tempered yellow lentil preparation", "110", "dal"),
    item("Daal Tadka", "Lentils with aromatic tempering", "120", "dal"),
    item("Daal Makhni", "Creamy slow cooked black lentils", "190", "dal"),

    # Rice
    item("Plain Rice", "Steamed fluffy white rice", "100", "rice"),
    item("Jeera", "Fragrant cumin flavored rice", "120", "rice"),
    item("Veg", "Flavorful mixed vegetable rice", "140", "rice"),
    item("Veg Pulao", "Aromatic rice with mixed vegetables", "140", "rice"),
    item("Paneer Biryani", "Aromatic biryani with paneer", "170", "rice"),
    item("Veg Biryani", "Fragrant biryani with vegetables", "150", "rice"),
    item("Veg Hyderabadi Biryani", "Hyderabadi style vegetable biryani", "180", "rice"),

    # Salad
    item("Green Salad", "Fresh assorted green salad", "50", "salad"),
    item("Onion Salad", "Fresh sliced onion salad", "40", "salad"),
    item("Mix Salad", "Fresh mixed vegetable salad", "50", "salad"),

    # Papad
    item("Fry Papad", "Crispy fried Indian papad", "35", "papad"),
    item("Dry Papad", "Crispy roasted Indian papad", "30", "papad"),
    item("Masala Papad", "Crispy papad with masala", "50", "papad"),

    # Raita
    item("Veg Raita", "Creamy raita with vegetables", "60", "raita"),
    item("Onion Raita", "Creamy raita with fresh onion", "70", "raita"),
    item("Boondi Raita", "Creamy raita with boondi", "50", "raita"),
    item("Mix Raita", "Creamy raita with mixed vegetables", "80", "raita"),

    # Snacks
    item("Paneer Pakoda", "Crispy paneer fritters", "110", "snacks"),
    item("Onion Pakoda", "Crispy spiced onion fritters", "100", "snacks"),
    item("Gobhi Pakoda", "Crispy cauliflower fritters", "90", "snacks"),
    item("Mix Veg Pakoda", "Crispy mixed vegetable fritters", "60", "snacks"),
    item("Aloo Pakoda", "Crispy spiced potato fritters", "70", "snacks"),
    item("Chola Bhature", "Spicy chickpeas with fluffy bhature", "110", "snacks"),
    item("Pav Bhaji", "Spiced vegetables with buttery pav", "110", "snacks"),
    item("Special Pav Bhaji", "Special spiced vegetables with pav", "180", "snacks"),
    item("Veg Burger", "Classic burger with vegetable patty", "80", "snacks"),
    item("Paneer Burger", "Burger with flavorful paneer patty", "90", "snacks"),
    item("Cheese Burger", "Cheesy burger with vegetable patty", "100", "snacks"),

    # Soup
    item("Veg Soup", "Warm soup with mixed vegetables", "90", "soup"),
    item("Hot and Shot Soup", "Spicy hot mixed vegetable soup", "110", "soup"),
    item("Manchow Soup", "Spicy Indo Chinese vegetable soup", "130", "soup"),

    # South Indian
    item("Paper Dosa", "Thin crispy South Indian dosa", "90", "south-indian"),
    item("Masala Dosa", "Crispy dosa with potato filling", "110", "south-indian"),
    item("Masoor Dosa", "Crispy dosa with masoor flavor", "120", "south-indian"),
    item("Onion Dosa", "Crispy dosa topped with onion", "110", "south-indian"),
    item("Masala Paneer Dosa", "Crispy dosa with paneer filling", "130", "south-indian"),
    item("Paneer Dosa", "Crispy dosa with paneer filling", "140", "south-indian"),
    item("Special Sawariya Dosa", "Signature dosa with special filling", "160", "south-indian"),
    item("Mix Uttapam", "Soft uttapam with mixed toppings", "150", "south-indian"),
    item("Paneer Uttapam", "Soft uttapam topped with paneer", "160", "south-indian"),
    item("Special Uttapam", "Special uttapam with assorted toppings", "170", "south-indian"),

    # Chinese variants table
    item("Manchurian Rice", "Indo Chinese rice with Manchurian", "170", "chinese"),
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
            Restaurant.name.ilike("%Sawariya%"),
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