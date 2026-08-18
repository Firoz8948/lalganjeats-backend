from __future__ import annotations

"""
Create/update Bikaner Rajasthan Sweets' menu.

The handwritten menu prices are treated as the seller transfer price
for 1 KG.

Variants:
    250g = 25% of 1 KG price
    500g = 50% of 1 KG price
    1 KG = original price

Pricing:
    display price = transfer price + 30%
    MRP           = transfer price + 39%

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.seed_rajasthan_menu

Preview without changing the database:
    docker compose exec backend python -m scripts.seed_rajasthan_menu --dry-run
"""

import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.core.database import SessionLocal

# Register every mapper the same way app.main does.
from app.modules.superadmin.models import (
    Tenant,
    DeliveryZone,
    DeliveryException,
)  # noqa: F401

from app.modules.users.models import (
    User,
    CustomerProfile,
    Address,
    CustomerSettings,
)  # noqa: F401

from app.modules.otp.models import OTP  # noqa: F401

from app.modules.restaurants.models import (
    CatalogCategory,
    CatalogSubcategory,
    Restaurant,
    MenuCategory,
    MenuItem,
    MenuItemVariant,
)

from app.modules.orders.models import (
    Order,
    OrderItem,
    DeliveryProfile,
    DeliveryOffer,
)  # noqa: F401

from app.modules.banners.models import HomeBannerSlide  # noqa: F401

from app.modules.payments.models import (
    PaymentSettings,
    RestaurantEarning,
    DeliveryEarning,
    Withdrawal,
    BankAccount,
)  # noqa: F401

from app.modules.promocodes.models import (
    PromoCode,
    PromoCodeUsage,
)  # noqa: F401

from app.modules.admin.models import (
    ImpersonationSession,
)  # noqa: F401

from app.modules.admin.reports.models import (
    ReportDelivery,
)  # noqa: F401

from app.modules.delivery_partner.models import (
    DeliveryPartnerDetails,
)  # noqa: F401


RESTAURANT_NAME = "Bikaner Rajasthan Sweets"
TENANT_SLUG = "lalganj"

DISPLAY_MARKUP = Decimal("1.30")
MRP_MARKUP = Decimal("1.39")
MONEY = Decimal("0.01")


SUBCATEGORIES = {
    "sweets": "Sweets",
    "namkeen": "Namkeen",
    "snacks": "Snacks",
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
    return tuple(
        Variant(label, Decimal(price))
        for label, price in pairs
    )


def kg_variants(price: str) -> tuple[Variant, ...]:
    """
    Convert a 1 KG price into:
        250g
        500g
        1 KG
    """

    kg_price = Decimal(price)

    price_250g = kg_price * Decimal("0.25")
    price_500g = kg_price * Decimal("0.50")

    return (
        Variant("250g", price_250g),
        Variant("500g", price_500g),
        Variant("1 KG", kg_price),
    )


def item_kg(
    name: str,
    description: str,
    kg_price: str,
    subcategory_slug: str,
) -> MenuRow:
    return MenuRow(
        name=name,
        description=description,
        subcategory_slug=subcategory_slug,
        variants=kg_variants(kg_price),
    )


def item(
    name: str,
    description: str,
    transfer_price: str,
    subcategory_slug: str,
) -> MenuRow:
    return MenuRow(
        name=name,
        description=description,
        subcategory_slug=subcategory_slug,
        variants=(
            Variant(
                "Regular",
                Decimal(transfer_price),
            ),
        ),
    )


ITEMS = [

    # ============================================================
    # SWEETS
    # ============================================================

    item_kg(
        "Gond Laddu",
        "Traditional gond sweet laddu",
        "1300",
        "sweets",
    ),

    item_kg(
        "Milk Cake",
        "Rich traditional milk cake",
        "1300",
        "sweets",
    ),

    item_kg(
        "Anjeer Barfi",
        "Rich fig flavored barfi",
        "1300",
        "sweets",
    ),

    item_kg(
        "Khoya Barfi",
        "Traditional creamy khoya barfi",
        "800",
        "sweets",
    ),

    item_kg(
        "Kaju Katli",
        "Classic smooth cashew sweet",
        "1000",
        "sweets",
    ),

    item_kg(
        "Mawa Barfi",
        "Rich creamy mawa barfi",
        "900",
        "sweets",
    ),

    item_kg(
        "Kaju Gajak",
        "Crunchy cashew gajak",
        "1300",
        "sweets",
    ),

    item_kg(
        "Kaju Laddu",
        "Rich cashew flavored laddu",
        "1300",
        "sweets",
    ),

    item_kg(
        "Kaju Roll",
        "Soft cashew filled roll",
        "1300",
        "sweets",
    ),

    item_kg(
        "Kaju Barfi",
        "Classic rich cashew barfi",
        "1300",
        "sweets",
    ),

    item_kg(
        "Chocolate Barfi",
        "Creamy chocolate flavored barfi",
        "800",
        "sweets",
    ),

    item_kg(
        "Kalakand",
        "Soft traditional milk sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Moti Pak",
        "Rich gram flour sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Boondi Barfi",
        "Traditional boondi based barfi",
        "500",
        "sweets",
    ),

    item_kg(
        "Peda",
        "Soft traditional milk peda",
        "500",
        "sweets",
    ),

    item_kg(
        "Balushahi",
        "Flaky syrup coated sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Malai Barfi",
        "Creamy milk based barfi",
        "500",
        "sweets",
    ),

    item_kg(
        "Kesar Barfi",
        "Saffron flavored creamy barfi",
        "500",
        "sweets",
    ),

    item_kg(
        "Gulab Jamun",
        "Soft syrup soaked sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Balushahi Special",
        "Traditional flaky sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Chandrakala",
        "Traditional stuffed sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Gujiya",
        "Sweet stuffed festive pastry",
        "500",
        "sweets",
    ),

    item_kg(
        "Milk Sweet",
        "Traditional milk based sweet",
        "200",
        "sweets",
    ),


    # ============================================================
    # RIGHT SIDE SWEETS
    # ============================================================

    item_kg(
        "Rajbhog",
        "Rich saffron milk sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Gulab Jamun Special",
        "Soft premium syrup sweet",
        "400",
        "sweets",
    ),

    item_kg(
        "Kesar Peda",
        "Saffron flavored milk peda",
        "400",
        "sweets",
    ),

    item_kg(
        "Kesar Milk Sweet",
        "Rich saffron milk sweet",
        "400",
        "sweets",
    ),

    item_kg(
        "Malai Peda",
        "Creamy traditional milk peda",
        "400",
        "sweets",
    ),

    item_kg(
        "Mawa Barfi Special",
        "Rich traditional mawa sweet",
        "400",
        "sweets",
    ),

    item_kg(
        "Kaju Barfi Special",
        "Premium cashew barfi",
        "400",
        "sweets",
    ),

    item_kg(
        "Rasgulla",
        "Soft Bengali style rasgulla",
        "500",
        "sweets",
    ),

    item_kg(
        "Rasmalai",
        "Soft milk soaked sweet",
        "500",
        "sweets",
    ),

    item_kg(
        "Chamcham",
        "Soft syrup soaked sweet",
        "400",
        "sweets",
    ),

    item_kg(
        "Doodh Peda",
        "Traditional rich milk peda",
        "500",
        "sweets",
    ),

    item_kg(
        "Gond Laddu Special",
        "Traditional gond enriched laddu",
        "220",
        "sweets",
    ),

    item_kg(
        "Dry Fruit Laddu",
        "Rich assorted dry fruit laddu",
        "260",
        "sweets",
    ),

    item_kg(
        "Panjiri",
        "Traditional nutritious sweet mix",
        "500",
        "sweets",
    ),


    # ============================================================
    # NAMKEEN
    # ============================================================

    item_kg(
        "Special Namkeen",
        "Crispy assorted savory mix",
        "200",
        "namkeen",
    ),


    # ============================================================
    # SNACKS
    # ============================================================

    item(
        "Pyaz Kachori",
        "Crispy onion stuffed kachori",
        "20",
        "snacks",
    ),

    item(
        "Masala Kachori",
        "Crispy spiced stuffed kachori",
        "20",
        "snacks",
    ),

    item(
        "Samosa",
        "Crispy spiced potato samosa",
        "30",
        "snacks",
    ),
]


def money(value: Decimal) -> Decimal:
    return value.quantize(
        MONEY,
        rounding=ROUND_HALF_UP,
    )


def normalize_name(value: str) -> str:
    return " ".join(
        (value or "").casefold().split()
    )


def find_restaurant(db) -> Restaurant:

    tenant = (
        db.query(Tenant)
        .filter(
            Tenant.slug == TENANT_SLUG
        )
        .one_or_none()
    )

    if tenant is None:
        raise RuntimeError(
            f"Tenant with slug '{TENANT_SLUG}' "
            f"was not found."
        )

    target = normalize_name(
        RESTAURANT_NAME
    )

    candidates = (
        db.query(Restaurant)
        .filter(
            Restaurant.tenant_id == tenant.id
        )
        .all()
    )

    matches = [
        row
        for row in candidates
        if normalize_name(row.name)
        == target
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple restaurants matching "
            f"'{RESTAURANT_NAME}' exist in tenant "
            f"'{TENANT_SLUG}'. "
            f"Aborting to avoid changing "
            f"the wrong restaurant."
        )

    names = ", ".join(
        f"#{row.id} {row.name!r}"
        for row in candidates
    ) or "none"

    raise RuntimeError(
        f"Exact restaurant "
        f"'{RESTAURANT_NAME}' was not found "
        f"in tenant '{TENANT_SLUG}'. "
        f"Available restaurants: {names}"
    )


def load_subcategories(
    db,
    restaurant: Restaurant,
) -> dict[str, CatalogSubcategory]:

    restaurant_category = (
        db.query(CatalogCategory)
        .filter(
            CatalogCategory.slug
            == "restaurant"
        )
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

        restaurant.business_category_id = (
            restaurant_category.id
        )

    elif (
        restaurant.business_category_id
        != restaurant_category.id
    ):

        raise RuntimeError(
            f"Restaurant #{restaurant.id} "
            f"is not assigned to the "
            f"Restaurant catalog category."
        )

    required = {
        row.subcategory_slug
        for row in ITEMS
    }

    rows = (
        db.query(CatalogSubcategory)
        .filter(
            CatalogSubcategory.category_id
            == restaurant_category.id,
            CatalogSubcategory.slug.in_(
                required
            ),
        )
        .all()
    )

    by_slug = {
        row.slug: row
        for row in rows
    }

    missing = sorted(
        required - by_slug.keys()
    )

    next_order = (
        max(
            (
                row.sort_order or 0
                for row in rows
            ),
            default=0,
        )
        + 1
    )

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
            MenuCategory.restaurant_id
            == restaurant_id,
            func.lower(
                MenuCategory.name
            )
            == subcategory.name.lower(),
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

    category = (
        get_or_create_menu_category(
            db,
            restaurant.id,
            subcategory,
        )
    )

    matches = (
        db.query(MenuItem)
        .filter(
            MenuItem.restaurant_id
            == restaurant.id,
            func.lower(
                MenuItem.name
            )
            == row.name.lower(),
        )
        .all()
    )

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple menu items named "
            f"{row.name!r} exist for "
            f"restaurant #{restaurant.id}. "
            f"Aborting instead of guessing."
        )

    menu_item = (
        matches[0]
        if matches
        else MenuItem(
            restaurant_id=restaurant.id
        )
    )

    action = (
        "updated"
        if matches
        else "created"
    )

    first = row.variants[0]

    display_price = money(
        first.transfer_price
        * DISPLAY_MARKUP
    )

    mrp = money(
        first.transfer_price
        * MRP_MARKUP
    )

    menu_item.category_id = category.id
    menu_item.business_subcategory_id = (
        subcategory.id
    )

    menu_item.name = row.name
    menu_item.description = (
        row.description
    )

    menu_item.actual_price = money(
        first.transfer_price
    )

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
        .filter(
            MenuItemVariant.menu_item_id
            == menu_item.id
        )
        .all()
    )

    by_label = {
        (v.label or "").casefold(): v
        for v in existing_variants
    }

    intended_labels = set()

    for sort_order, variant_data in enumerate(
        row.variants
    ):

        label = variant_data.label
        transfer = (
            variant_data.transfer_price
        )

        variant_display = money(
            transfer * DISPLAY_MARKUP
        )

        variant_mrp = money(
            transfer * MRP_MARKUP
        )

        variant = by_label.get(
            label.casefold()
        )

        if variant is None:

            variant = MenuItemVariant(
                menu_item_id=menu_item.id,
                label=label,
            )

            db.add(variant)

        variant.actual_price = money(
            transfer
        )

        variant.price = variant_display
        variant.original_price = (
            variant_mrp
        )

        variant.sort_order = (
            sort_order
        )

        variant.is_available = True
        variant.is_deleted = False

        intended_labels.add(
            label.casefold()
        )

        print(
            f"{action:7} "
            f"{row.name:<40} "
            f"[{label:<6}] "
            f"transfer=₹{transfer:.2f} "
            f"display=₹{variant_display:.2f} "
            f"MRP=₹{variant_mrp:.2f} "
            f"[{subcategory.name}]"
        )

    # Retire stale variants so old sizes/options
    # are not still shown.
    for variant in existing_variants:

        if (
            (variant.label or "").casefold()
            not in intended_labels
        ):

            variant.is_available = False
            variant.is_deleted = True

    return action


def seed(
    dry_run: bool = False,
) -> None:

    if not ITEMS:
        raise RuntimeError(
            "No menu items defined."
        )

    db = SessionLocal()

    try:

        restaurant = find_restaurant(db)

        subcategories = load_subcategories(
            db,
            restaurant,
        )

        print(
            f"Restaurant: #{restaurant.id} "
            f"{restaurant.name} "
            f"(tenant_id="
            f"{restaurant.tenant_id})"
        )

        print(
            "Pricing: "
            "display = transfer + 30%; "
            "MRP = transfer + 39%; "
            f"items={len(ITEMS)}"
        )

        created = 0
        updated = 0

        for row in ITEMS:

            action = upsert_item(
                db,
                restaurant,
                row,
                subcategories[
                    row.subcategory_slug
                ],
            )

            if action == "created":
                created += 1
            else:
                updated += 1

        if dry_run:

            db.rollback()

            print(
                f"DRY RUN: rolled back "
                f"{created} create(s), "
                f"{updated} update(s)."
            )

        else:

            db.commit()

            print(
                f"Done: "
                f"{created} item(s) created, "
                f"{updated} item(s) updated."
            )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and print changes, "
            "then roll them back."
        ),
    )

    args = parser.parse_args()

    seed(
        dry_run=args.dry_run
    )