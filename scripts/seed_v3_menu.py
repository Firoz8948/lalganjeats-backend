from __future__ import annotations

"""
Replace V3 South Indian Family Restaurants' menu.

Pricing:
    display price = transfer price + ₹5
    MRP           = display price + 5%

Half / Full only on Veg Biryani and V3 Special Veg Biryani.
All other items are a single price (no size picker).

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_v3_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_v3_menu --dry-run
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
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
DISPLAY_ADD = Decimal("5")
MRP_ON_DISPLAY = Decimal("1.05")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "breakfast": "Breakfast",
    "south-indian": "South Indian",
    "chinese": "Chinese",
    "snacks": "Snacks",
    "samosa": "Samosa",
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
    # Breakfast
    item(
        "Aloo Paratha",
        "Indian flatbread stuffed with spiced potato filling.",
        "50",
        "breakfast",
    ),
    item(
        "Mix Paratha",
        "Soft paratha filled with a flavorful mixed stuffing.",
        "80",
        "breakfast",
    ),
    item(
        "Gobi Paratha",
        "Crispy paratha stuffed with seasoned cauliflower.",
        "70",
        "breakfast",
    ),
    item(
        "Paneer Paratha",
        "Delicious paratha stuffed with seasoned paneer.",
        "90",
        "breakfast",
    ),
    item(
        "Golgappa Puri",
        "Crispy puris perfect for preparing delicious golgappas.",
        "60",
        "breakfast",
    ),
    item(
        "Chola Bhatura",
        "Fluffy bhatura served with flavorful spiced chickpeas.",
        "80",
        "breakfast",
    ),
    item(
        "Chola Paratha",
        "Indian paratha served with flavorful chola preparation.",
        "60",
        "breakfast",
    ),
    item(
        "Omelette Paratha",
        "Fluffy omelette paired with a freshly prepared paratha.",
        "70",
        "breakfast",
    ),
    item(
        "V3 Special Chola Puri",
        "Special V3-style chola puri prepared fresh.",
        "30",
        "breakfast",
    ),

    # South Indian
    item(
        "Plain Dosa",
        "Crispy golden dosa served with classic South Indian accompaniments.",
        "90",
        "south-indian",
    ),
    item(
        "Masala Dosa",
        "Crispy dosa filled with delicious spiced potato masala.",
        "120",
        "south-indian",
    ),
    item(
        "Paneer Dosa",
        "Crispy dosa filled with flavorful seasoned paneer.",
        "140",
        "south-indian",
    ),
    item(
        "Onion Dosa",
        "Crispy dosa topped with flavorful onions.",
        "120",
        "south-indian",
    ),
    item(
        "Masala Idli Dosa (3 pcs)",
        "Soft idli served with a flavorful masala preparation.",
        "60",
        "south-indian",
    ),
    item(
        "Dahi Vada",
        "Soft lentil vadas topped with creamy seasoned yogurt.",
        "90",
        "south-indian",
    ),
    item(
        "Medu Vada (3 pcs)",
        "Crispy golden South Indian lentil fritters with a soft center.",
        "60",
        "south-indian",
    ),
    item(
        "V3 Special Paneer Masala Dosa",
        "Special dosa loaded with paneer and flavorful masala.",
        "170",
        "south-indian",
    ),
    item(
        "V3 Special Dahi Vada (2 pcs)",
        "Special soft vadas served with creamy seasoned yogurt.",
        "60",
        "south-indian",
    ),

    # Chinese
    item(
        "Veg Manchurian Dry",
        "Crispy vegetable balls tossed in flavorful Indo-Chinese sauces.",
        "110",
        "chinese",
    ),
    item(
        "Paneer 65",
        "Crispy paneer tossed with spicy and aromatic 65-style seasoning.",
        "170",
        "chinese",
    ),
    item(
        "Chilli Paneer",
        "Paneer tossed with chillies, onions and flavorful Chinese sauces.",
        "130",
        "chinese",
    ),
    item(
        "Veg Manchurian Gravy",
        "Vegetable Manchurian served in a rich, flavorful gravy.",
        "120",
        "chinese",
    ),

    # Snacks
    item(
        "Finger Chips",
        "Crispy golden French fries seasoned for a delicious taste.",
        "50",
        "snacks",
    ),
    item(
        "Paneer Maggi",
        "Hot Maggi noodles cooked with delicious pieces of paneer.",
        "50",
        "snacks",
    ),
    item(
        "Masala Maggi",
        "Spicy and flavorful Maggi noodles cooked with special masala.",
        "70",
        "snacks",
    ),
    item(
        "Pyaz Pakodi",
        "Crispy onion fritters coated in seasoned gram flour.",
        "40",
        "snacks",
    ),
    item(
        "Paneer Pakoda (6 pcs)",
        "Crispy gram-flour coated paneer fritters.",
        "90",
        "snacks",
    ),
    item(
        "Bread Pakoda (2 pcs)",
        "Crispy bread fritters with a flavorful spiced filling.",
        "50",
        "snacks",
    ),
    item(
        "V3 Special Maggi",
        "Special V3-style Maggi prepared with a flavorful twist.",
        "80",
        "snacks",
    ),

    # Samosa
    item(
        "Aloo Samosa",
        "Crispy pastry filled with delicious spiced potato.",
        "50",
        "samosa",
    ),
    item(
        "Onion Samosa",
        "Crispy samosa filled with flavorful seasoned onion.",
        "50",
        "samosa",
    ),
    item(
        "Corn Samosa",
        "Crispy samosa filled with a delicious sweet-corn mixture.",
        "60",
        "samosa",
    ),

    # Rice — only these two have Half / Full
    item(
        "Veg Fried Rice",
        "Stir-fried rice tossed with fresh vegetables and sauces.",
        "120",
        "rice",
    ),
    item(
        "Paneer Fried Rice",
        "Flavorful fried rice loaded with paneer and vegetables.",
        "140",
        "rice",
    ),
    item(
        "Veg Manchurian Fried Rice",
        "Fried rice combined with delicious vegetable Manchurian.",
        "150",
        "rice",
    ),
    item(
        "Chola Rice",
        "Flavorful rice preparation served with spiced chola.",
        "120",
        "rice",
    ),
    item(
        "V3 Special Lemon Rice",
        "Aromatic rice infused with fresh, tangy lemon flavor.",
        "170",
        "rice",
    ),
    item_named(
        "Veg Biryani",
        "Fragrant basmati rice cooked with vegetables and aromatic spices.",
        "rice",
        ("Half", "110"),
        ("Full", "170"),
    ),
    item_named(
        "V3 Special Veg Biryani",
        "Special vegetable biryani prepared with rich aromatic spices.",
        "rice",
        ("Half", "170"),
        ("Full", "210"),
    ),
]


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def prices_from_transfer(transfer: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    transfer = money(transfer)
    display = money(transfer + DISPLAY_ADD)
    mrp = money(display * MRP_ON_DISPLAY)
    return transfer, display, mrp


def persist_size_variants(row: MenuRow) -> bool:
    """Half/Full (or any named sizes). A lone Regular is item-level only."""
    if len(row.variants) > 1:
        return True
    if len(row.variants) == 1 and row.variants[0].label.casefold() != "regular":
        return True
    return False


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
    transfer, display_price, mrp = prices_from_transfer(first.transfer_price)

    menu_item.category_id = category.id
    menu_item.business_subcategory_id = subcategory.id
    menu_item.name = row.name
    menu_item.description = row.description
    menu_item.actual_price = transfer
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
    intended_labels: set[str] = set()
    keep_sizes = persist_size_variants(row)

    if keep_sizes:
        for sort_order, variant_data in enumerate(row.variants):
            label = variant_data.label
            transfer, variant_display, variant_mrp = prices_from_transfer(
                variant_data.transfer_price
            )
            variant = by_label.get(label.casefold())
            if variant is None:
                variant = MenuItemVariant(
                    menu_item_id=menu_item.id,
                    label=label,
                )
                db.add(variant)

            variant.actual_price = transfer
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
    else:
        print(
            f"{action:7} {row.name:<48} "
            f"transfer=₹{transfer:.2f} "
            f"display=₹{display_price:.2f} "
            f"MRP=₹{mrp:.2f} "
            f"[{subcategory.name}]"
        )

    for variant in existing_variants:
        if (variant.label or "").casefold() not in intended_labels:
            variant.is_available = False
            variant.is_deleted = True

    return action


def retire_unlisted_items(db, restaurant: Restaurant) -> int:
    intended = {normalize_name(row.name) for row in ITEMS}
    rows = (
        db.query(MenuItem)
        .filter(
            MenuItem.restaurant_id == restaurant.id,
            MenuItem.is_deleted == False,
        )
        .all()
    )
    retired = 0
    now = datetime.now(timezone.utc)
    for menu_item in rows:
        if normalize_name(menu_item.name) in intended:
            continue
        menu_item.is_deleted = True
        menu_item.is_available = False
        menu_item.deleted_at = now
        retired += 1
        print(f"retired {menu_item.name}")
        for variant in (
            db.query(MenuItemVariant)
            .filter(MenuItemVariant.menu_item_id == menu_item.id)
            .all()
        ):
            variant.is_available = False
            variant.is_deleted = True
    return retired


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
            "Pricing: display = transfer + ₹5; "
            f"MRP = display + 5%; items={len(ITEMS)}"
        )

        retired = retire_unlisted_items(db, restaurant)
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
                f"DRY RUN: rolled back {retired} retire(s), "
                f"{created} create(s), {updated} update(s)."
            )
        else:
            db.commit()
            print(
                f"Done: {retired} old item(s) cleared, "
                f"{created} item(s) created, {updated} item(s) updated."
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
