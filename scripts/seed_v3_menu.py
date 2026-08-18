from __future__ import annotations

"""
Create/update V3 South Indian Family Restaurants' menu.

The printed menu price is treated as the seller transfer price:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_v3_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_v3_menu --dry-run
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


RESTAURANT_NAME = "V3 South Indian Family Restaurants"
TENANT_SLUG = "lalganj"
DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")




SUBCATEGORIES = {
    "breakfast": "Breakfast",
    "south-indian": "South Indian",
    "starters": "Starters",
    "noodles": "Noodles",
    "rice": "Rice",
    "dal": "Dal",
    "sabzi": "Sabzi",
    "paneer-dishes": "Paneer Dishes",
    "roti": "Roti",
    "raita": "Raita",
    "papad": "Papad",
    "salad": "Salad",
    "thali": "Thali",
    "lassi": "Lassi",
    "dessert": "Dessert",
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
    # Breakfast
    item("Aloo Paratha", "Potato stuffed Indian flatbread", "50", "breakfast"),
    item("Mix Paratha", "Mixed vegetable stuffed flatbread", "80", "breakfast"),
    item("Gobhi Paratha", "Cauliflower stuffed Indian flatbread", "70", "breakfast"),
    item("Paneer Paratha", "Paneer stuffed Indian flatbread", "90", "breakfast"),
    item("Chhola Puri", "Spiced chickpeas with puris", "50", "breakfast"),
    item("Chhola Bhatura", "Spicy chickpeas with fluffy bhatura", "70", "breakfast"),
    item("Chhola Paratha", "Chickpea stuffed Indian flatbread", "50", "breakfast"),
    item("Onion Paratha", "Onion stuffed Indian flatbread", "70", "breakfast"),
    item("Pav Bhaji", "Spiced vegetables with buttery pav", "70", "breakfast"),

    # South Indian
    item("Plain Dosa", "Crispy classic South Indian dosa", "80", "south-indian"),
    item("Masala Dosa", "Crispy dosa with potato filling", "110", "south-indian"),
    item("Paneer Dosa", "Crispy dosa with paneer filling", "130", "south-indian"),
    item("Onion Dosa", "Crispy dosa topped with onion", "110", "south-indian"),
    item("Idli Sambhar", "Soft idli with flavorful sambhar", "50", "south-indian"),
    item("Masala Idli Sambhar", "Spiced idli with flavorful sambhar", "60", "south-indian"),
    item("Vada Sambhar", "Crispy lentil vada with sambhar", "50", "south-indian"),
    item("Idli Vada Combo Sambhar", "Idli vada served with sambhar", "40", "south-indian"),
    item("Onion Uttapam", "Soft uttapam topped with onion", "90", "south-indian"),
    item("Dal Vada", "Crispy lentil fritters", "50", "south-indian"),
    item("V3 Special Paneer Masala Dosa", "Special dosa with paneer masala", "150", "south-indian"),
    item("V3 Special Dahi Vada", "Special vada with creamy curd", "60", "south-indian"),
    item("V3 Special Kela Paratha", "Special banana stuffed paratha", "30", "south-indian"),

    # Starters
    item("Finger Chips", "Crispy golden potato fries", "40", "starters"),
    item("Aloo Chips", "Crispy seasoned potato chips", "50", "starters"),
    item("Plain Maggi", "Classic masala instant noodles", "40", "starters"),
    item("Masala Maggi", "Spicy masala instant noodles", "60", "starters"),
    item("Mirchi Pakoda", "Crispy spiced chilli fritters", "10", "starters"),
    item_named("Onion Pakoda", "Crispy spiced onion fritters", "starters",
               ("Half", "40"), ("Full", "90")),
    item("Paneer Pakoda", "Crispy paneer fritters", "90", "starters"),
    item("Bread Pakoda", "Crispy stuffed bread fritter", "40", "starters"),
    item("V3 Special Maggi", "Loaded signature masala Maggi", "80", "starters"),

    # Noodles
    item("Veg Noodles", "Stir fried vegetable noodles", "110", "noodles"),
    item("Paneer Noodles", "Stir fried paneer noodles", "130", "noodles"),
    item("V3 Special Noodles", "Signature loaded stir fried noodles", "150", "noodles"),

    # Rice
    item_named("Steam Rice", "Steamed fluffy white rice", "rice",
               ("Half", "40"), ("Full", "70")),
    item_named("Jeera Rice", "Fragrant cumin flavored rice", "rice",
               ("Half", "70"), ("Full", "110")),
    item_named("Veg Pulao", "Aromatic rice with mixed vegetables", "rice",
               ("Half", "80"), ("Full", "130")),
    item_named("Veg Biryani", "Fragrant biryani with vegetables", "rice",
               ("Half", "90"), ("Full", "150")),
    item_named("V3 Special Veg Biryani", "Special loaded vegetable biryani", "rice",
               ("Half", "110"), ("Full", "170")),

    # Dal
    item_named("Dal Fry", "Tempered yellow lentil preparation", "dal",
               ("Half", "60"), ("Full", "110")),
    item_named("Dal Tadka", "Lentils with aromatic tempering", "dal",
               ("Half", "70"), ("Full", "120")),
    item_named("Jeera Dal", "Lentils with cumin tempering", "dal",
               ("Half", "70"), ("Full", "120")),
    item_named("Dal Fry Butter", "Creamy buttery lentil preparation", "dal",
               ("Half", "80"), ("Full", "130")),

    # Sabzi
    item_named("Mix Veg", "Mixed vegetables in flavorful gravy", "sabzi",
               ("Half", "70"), ("Full", "120")),
    item_named("Aloo Matar", "Potatoes cooked with green peas", "sabzi",
               ("Half", "80"), ("Full", "130")),
    item_named("Aloo Gobhi", "Potatoes with cauliflower curry", "sabzi",
               ("Half", "80"), ("Full", "130")),
    item_named("Aloo Jeera", "Potatoes tempered with cumin", "sabzi",
               ("Half", "60"), ("Full", "110")),

    # Paneer Dishes
    item_named("Kadhai Paneer", "Spiced paneer in kadhai gravy", "paneer-dishes",
               ("Half", "140"), ("Full", "210")),
    item_named("Paneer Butter Masala", "Creamy paneer butter curry", "paneer-dishes",
               ("Half", "150"), ("Full", "230")),
    item_named("Palak Paneer", "Paneer cooked in spinach gravy", "paneer-dishes",
               ("Half", "140"), ("Full", "210")),
    item_named("Matar Paneer", "Paneer cooked with green peas", "paneer-dishes",
               ("Half", "130"), ("Full", "190")),
    item_named("Shahi Paneer", "Rich creamy royal paneer curry", "paneer-dishes",
               ("Half", "150"), ("Full", "230")),
    item("Kaju Korma", "Rich creamy cashew curry", "260", "paneer-dishes"),
    item("Paneer Bhurji", "Spiced scrambled paneer preparation", "240", "paneer-dishes"),
    item("V3 Special Paneer", "Signature special paneer curry", "300", "paneer-dishes"),

    # Roti
    item("Tawa Roti", "Soft freshly cooked tawa roti", "8", "roti"),
    item("Tawa Butter Roti", "Soft roti topped with butter", "12", "roti"),
    item("Desi Ghee Tawa Roti", "Tawa roti with desi ghee", "15", "roti"),
    item("Tandoori Roti", "Crispy tandoor baked Indian bread", "10", "roti"),
    item("Tandoori Butter Roti", "Buttery tandoor baked Indian bread", "15", "roti"),
    item("Tandoori Ghee Roti", "Tandoori roti with desi ghee", "20", "roti"),

    # Raita
    item("Plain Dahi", "Fresh creamy plain curd", "25", "raita"),
    item("Plain Raita", "Creamy seasoned yogurt raita", "30", "raita"),
    item("Mix Veg Raita", "Creamy raita with mixed vegetables", "60", "raita"),
    item("Cucumber Raita", "Refreshing raita with cucumber", "50", "raita"),
    item("Boondi Raita", "Creamy raita with boondi", "50", "raita"),

    # Papad
    item("Dry Papad", "Crispy roasted Indian papad", "25", "papad"),
    item("Fry Papad", "Crispy fried Indian papad", "25", "papad"),
    item("Masala Papad", "Crispy papad with masala", "30", "papad"),

    # Salad
    item("Onion Salad", "Fresh sliced onion salad", "30", "salad"),
    item("Green Salad", "Fresh assorted green salad", "40", "salad"),
    item("Cucumber Salad", "Fresh sliced cucumber salad", "50", "salad"),
    item("Tomato Salad", "Fresh sliced tomato salad", "30", "salad"),
    item("Kheera Salad", "Fresh cucumber salad", "30", "salad"),

    # Thali
    item("Plain Thali", "Dal rice vegetables roti", "140", "thali"),
    item("Rajasthani Special Thali", "Traditional Rajasthani meal platter", "200", "thali"),
    item("V3 Special Thali", "Signature complete Indian meal", "230", "thali"),

    # Lassi (kept because user asked to remove chai/coffee/water/lemon-water/tea,
    # but did not ask to remove lassi)
    item("Namkeen Lassi", "Refreshing salted yogurt drink", "50", "lassi"),
    item("Meethi Lassi", "Sweet creamy yogurt drink", "60", "lassi"),

    # Dessert
    item("V3 Special Kheer", "Creamy traditional rice pudding", "70", "dessert"),
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
            Restaurant.name.ilike("%V3%"),
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