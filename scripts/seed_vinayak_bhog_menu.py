from __future__ import annotations

"""
Create/update Vinayak Bhog Family Restaurants' menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_vinayak_bhog_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_vinayak_bhog_menu --dry-run
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


RESTAURANT_NAME = "Vinayak Bhog Family Restaurants"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "chinese": "Chinese",
    "paneer": "Paneer",
    "snacks-starters": "Snacks / Starters",
    "breakfast": "Breakfast",
    "soup": "Soup",
    "dosa": "Dosa",
    "pizza": "Pizza",
    "burger": "Burger",
    "roti-naan": "Roti & Naan",
    "rice-biryani": "Rice & Biryani",
    "salad-raita": "Salad / Raita",
    "beverages": "Beverages",
    "desserts": "Desserts",
    "thali": "Thali",
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
    item("Veg Chowmein", "Stir fried vegetable noodles", "130", "chinese"),
    item("Paneer Chowmein", "Paneer tossed chowmein noodles", "170", "chinese"),
    item("Mushroom Chowmein", "Mushroom tossed chowmein noodles", "160", "chinese"),
    item("Singapuri Noodles", "Spicy Singapore style noodles", "170", "chinese"),
    item("Hakka Noodles", "Classic stir fried hakka noodles", "190", "chinese"),
    item("Schezwan Noodles", "Spicy Schezwan style noodles", "190", "chinese"),
    item("Garlic Noodles", "Garlic flavored stir fried noodles", "190", "chinese"),
    item("Fried Rice", "Stir fried seasoned rice", "150", "chinese"),
    item("Paneer Fried Rice", "Paneer tossed fried rice", "170", "chinese"),
    item("Schezwan Rice", "Spicy Schezwan fried rice", "190", "chinese"),
    item("Garlic Rice", "Garlic flavored fried rice", "190", "chinese"),
    item_named("Veg Manchurian", "Crispy vegetable Manchurian", "chinese",
               ("Gravy", "200"), ("Dry", "220")),
    item_named("Paneer Manchurian", "Spicy paneer Manchurian", "chinese",
               ("Gravy", "220"), ("Dry", "240")),
    item_named("Chilli Paneer", "Spicy chilli paneer", "chinese",
               ("Gravy", "240"), ("Dry", "250")),
    item("Mushroom Chilli", "Spicy chilli mushroom", "270", "chinese"),

    # Paneer
    item_named("Kadhai Paneer", "Spicy paneer with peppers", "paneer",
               ("Half", "150"), ("Full", "260")),
    item_named("Matar Paneer", "Peas cooked with paneer", "paneer",
               ("Half", "140"), ("Full", "250")),
    item_named("Paneer Butter Masala", "Creamy buttery paneer curry", "paneer",
               ("Half", "170"), ("Full", "270")),
    item("Shahi Paneer", "Rich creamy royal paneer", "280", "paneer"),
    item("Paneer Kaju Masala", "Paneer with cashew rich gravy", "290", "paneer"),
    item("Paneer Angara", "Smoky spicy paneer curry", "270", "paneer"),
    item("Paneer Malai Kofta", "Creamy paneer kofta curry", "260", "paneer"),
    item("Paneer Do Pyaza", "Paneer with onion gravy", "250", "paneer"),
    item("Paneer Lababdar", "Creamy tangy paneer gravy", "280", "paneer"),
    item("Handi Paneer", "Rich handi style paneer", "250", "paneer"),
    item("Handi Mushroom", "Mushroom in rich handi gravy", "270", "paneer"),
    item("Kaju Masala", "Cashew nuts in rich gravy", "250", "paneer"),

    # Snacks / Starters
    item("Paneer Pakoda (6 Pcs)", "Crispy paneer fritters", "210", "snacks-starters"),
    item("Veg Pakoda (6 Pcs)", "Crispy vegetable fritters", "90", "snacks-starters"),
    item("Onion Pakoda (6 Pcs)", "Crispy onion fritters", "90", "snacks-starters"),
    item("Mix Pakoda (6 Pcs)", "Mixed vegetable crispy fritters", "110", "snacks-starters"),
    item("Paneer 65", "Crispy spicy paneer bites", "260", "snacks-starters"),
    item("Paneer Spring Roll", "Crispy paneer spring rolls", "160", "snacks-starters"),
    item("Chilli Potato", "Crispy spicy chilli potato", "170", "snacks-starters"),
    item("Honey Chilli Potato", "Sweet spicy chilli potato", "190", "snacks-starters"),
    item("Finger Chips", "Crispy golden potato fries", "100", "snacks-starters"),
    item("Veg Roll", "Vegetable stuffed crispy roll", "140", "snacks-starters"),
    item("Paneer Roll", "Paneer stuffed crispy roll", "150", "snacks-starters"),

    # Breakfast
    item("Mix Paratha", "Flavorful mixed vegetable paratha", "140", "breakfast"),
    item("Aloo Paratha", "Potato stuffed Indian paratha", "90", "breakfast"),
    item("Paneer Paratha", "Paneer stuffed Indian paratha", "130", "breakfast"),
    item("Ajwain Paratha", "Ajwain flavored Indian paratha", "110", "breakfast"),
    item("Methi Paratha", "Fresh fenugreek flavored paratha", "120", "breakfast"),

    # Soup
    item("Veg Soup", "Light mixed vegetable soup", "90", "soup"),
    item("Hot & Sour Soup", "Tangy spicy vegetable soup", "110", "soup"),
    item("Manchow Soup", "Spicy Indo Chinese soup", "120", "soup"),
    item("Mushroom Soup", "Creamy mushroom soup", "120", "soup"),

    # Dosa / Uttapam
    item("Plain Dosa", "Crispy plain rice crepe", "99", "dosa"),
    item("Masala Dosa", "Crispy dosa with potato", "139", "dosa"),
    item("Paneer Masala Dosa", "Paneer stuffed masala dosa", "170", "dosa"),
    item("Special Vinayak Bhog Dosa", "Signature special stuffed dosa", "210", "dosa"),
    item("Veg Uttapam", "Soft uttapam with vegetables", "120", "dosa"),
    item("Paneer Uttapam", "Soft uttapam with paneer", "170", "dosa"),
    item("Special Uttapam", "Signature special vegetable uttapam", "199", "dosa"),

    # Pizza
    item("Margherita Pizza", "Classic cheese tomato pizza", "120", "pizza"),
    item("Veg Pizza", "Loaded vegetable cheese pizza", "160", "pizza"),
    item("Capsicum Pizza", "Fresh capsicum topped pizza", "180", "pizza"),
    item("Tomato Pizza", "Fresh tomato topped pizza", "170", "pizza"),
    item("Paneer Pizza", "Paneer topped cheese pizza", "210", "pizza"),
    item("Chilli Paneer Pizza", "Spicy chilli paneer pizza", "260", "pizza"),
    item("Chilli Mushroom Pizza", "Spicy mushroom chilli pizza", "260", "pizza"),
    item("Mix Pizza", "Mixed topping cheese pizza", "250", "pizza"),
    item("Special Vinayak Bhog Pizza", "Signature loaded special pizza", "299", "pizza"),

    # Burger
    item("Veg Burger", "Classic vegetable patty burger", "80", "burger"),
    item("Paneer Cheese Burger", "Paneer burger with cheese", "110", "burger"),
    item("Paneer Burger", "Classic paneer patty burger", "99", "burger"),
    item("Cheese Corn Burger", "Corn burger with melted cheese", "120", "burger"),

    # Roti & Naan
    item("Tawa Roti", "Fresh soft tawa wheat roti", "12", "roti-naan"),
    item("Butter Roti", "Soft roti with butter", "18", "roti-naan"),
    item("Missi Roti", "Gram flour spiced roti", "45", "roti-naan"),
    item("Plain Naan", "Soft classic tandoori naan", "40", "roti-naan"),
    item("Butter Naan", "Soft buttery tandoori naan", "50", "roti-naan"),
    item("Laccha Paratha", "Flaky layered Indian paratha", "50", "roti-naan"),
    item("Garlic Naan", "Garlic flavored tandoori naan", "70", "roti-naan"),
    item("Stuffed Naan", "Stuffed soft tandoori naan", "80", "roti-naan"),

    # Rice & Biryani
    item_named("Steam Rice", "Steamed aromatic rice", "rice-biryani",
               ("Half", "60"), ("Full", "100")),
    item_named("Jeera Rice", "Cumin flavored basmati rice", "rice-biryani",
               ("Half", "80"), ("Full", "140")),
    item_named("Matar Pulao", "Fragrant peas pulao rice", "rice-biryani",
               ("Half", "90"), ("Full", "160")),
    item_named("Veg Biryani", "Aromatic vegetable dum biryani", "rice-biryani",
               ("Half", "90"), ("Full", "170")),
    item_named("Paneer Biryani", "Paneer dum biryani rice", "rice-biryani",
               ("Half", "110"), ("Full", "190")),

    # Salad / Raita
    item("Green Salad", "Fresh seasonal vegetable salad", "80", "salad-raita"),
    item("Russian Salad", "Creamy mixed vegetable salad", "70", "salad-raita"),
    item("Fried Papad", "Crispy fried papad", "30", "salad-raita"),
    item("Roasted Papad", "Crispy roasted papad", "40", "salad-raita"),
    item("Masala Papad", "Crispy papad with masala", "80", "salad-raita"),
    item("Cucumber Raita", "Cool cucumber yogurt raita", "80", "salad-raita"),
    item("Mix Raita", "Mixed vegetable yogurt raita", "90", "salad-raita"),
    item("Vegetable Raita", "Fresh vegetable yogurt raita", "90", "salad-raita"),
    item("Fruit Raita", "Sweet mixed fruit raita", "120", "salad-raita"),

    # Beverages
    item("Tea", "Hot refreshing Indian tea", "20", "beverages"),
    item("Special Tea", "Special aromatic milk tea", "25", "beverages"),
    item("Coffee", "Hot creamy brewed coffee", "50", "beverages"),
    item("Cold Coffee", "Chilled creamy cold coffee", "100", "beverages"),
    item("Lassi", "Refreshing chilled sweet lassi", "80", "beverages"),

    # Desserts
    item("Gulab Jamun", "Warm syrupy gulab jamun", "20", "desserts"),

    # Thali
    item("Simple Thali", "Complete Indian meal platter", "150", "thali"),
    item("Special Vinayak Bhog Thali", "Complete special Indian thali", "250", "thali"),
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
            f"{action:7} {row.name:<42} [{label:<8}] "
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