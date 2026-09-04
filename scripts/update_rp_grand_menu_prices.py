from __future__ import annotations

"""
Raise Hotel RP Grand & Restaurants existing menu prices in the database.

    transfer (actual_price) = existing transfer + 5%
    display (price)         = existing display + 5%
    MRP (original_price)    = existing display + 6%

Applies to every current menu item and variant (breakfast + later batches).

Run on EC2 inside the backend container:
    docker compose exec backend python -m scripts.update_rp_grand_menu_prices

Preview without changing the database:
    docker compose exec backend python -m scripts.update_rp_grand_menu_prices --dry-run
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal

from app.modules.superadmin.models import Tenant, DeliveryZone, DeliveryException  # noqa: F401
from app.modules.users.models import User, CustomerProfile, Address, CustomerSettings  # noqa: F401
from app.modules.otp.models import OTP  # noqa: F401
from app.modules.restaurants.models import Restaurant, MenuItem, MenuItemVariant
from app.modules.orders.models import Order, OrderItem, DeliveryProfile, DeliveryOffer  # noqa: F401
from app.modules.banners.models import HomeBannerSlide  # noqa: F401
from app.modules.payments.models import (  # noqa: F401
    PaymentSettings,
    RestaurantEarning,
    DeliveryEarning,
    Withdrawal,
    BankAccount,
)
from app.modules.promocodes.models import PromoCode, PromoCodeUsage  # noqa: F401
from app.modules.admin.models import ImpersonationSession  # noqa: F401
from app.modules.admin.reports.models import ReportDelivery  # noqa: F401
from app.modules.delivery_partner.models import DeliveryPartnerDetails  # noqa: F401


RESTAURANT_NAME = "Hotel RP Grand & Restaurants"
TENANT_SLUG = "lalganj"
TRANSFER_MARKUP = Decimal("1.05")
DISPLAY_MARKUP = Decimal("1.05")
MRP_FROM_DISPLAY = Decimal("1.06")
MONEY = Decimal("0.01")


def money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def find_restaurant(db) -> Restaurant:
    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.name.ilike("%RP Grand%"))
        .order_by(Restaurant.id.asc())
        .all()
    )
    if not restaurant:
        raise RuntimeError(f"Restaurant matching {RESTAURANT_NAME!r} was not found.")
    if len(restaurant) > 1:
        names = ", ".join(f"#{r.id} {r.name}" for r in restaurant)
        raise RuntimeError(f"Multiple RP Grand restaurants found: {names}")
    return restaurant[0]


def bump_prices(actual, display) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    old_transfer = to_decimal(actual)
    old_display = to_decimal(display)
    new_transfer = money(old_transfer * TRANSFER_MARKUP) if old_transfer is not None else None
    new_display = money(old_display * DISPLAY_MARKUP) if old_display is not None else None
    new_mrp = money(old_display * MRP_FROM_DISPLAY) if old_display is not None else None
    if new_display is not None and new_mrp is not None and new_mrp < new_display:
        new_mrp = new_display
    return new_transfer, new_display, new_mrp


def update_prices(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        restaurant = find_restaurant(db)
        items = (
            db.query(MenuItem)
            .options(joinedload(MenuItem.variants))
            .filter(
                MenuItem.restaurant_id == restaurant.id,
                MenuItem.is_deleted.is_(False),
            )
            .order_by(MenuItem.id.asc())
            .all()
        )
        if not items:
            raise RuntimeError(f"No menu items found for #{restaurant.id} {restaurant.name}")

        print(
            f"Restaurant: #{restaurant.id} {restaurant.name} "
            f"(tenant_id={restaurant.tenant_id})"
        )
        print(
            "Pricing: transfer = existing transfer + 5%; "
            "display = existing display + 5%; "
            "MRP = existing display + 6%"
        )
        print(f"Items: {len(items)}")

        updated_items = 0
        updated_variants = 0

        for item in items:
            live_variants = [
                variant
                for variant in (item.variants or [])
                if not variant.is_deleted
            ]
            live_variants.sort(key=lambda variant: (variant.sort_order or 0, variant.id or 0))

            if live_variants:
                for variant in live_variants:
                    new_transfer, new_display, new_mrp = bump_prices(
                        variant.actual_price,
                        variant.price,
                    )
                    print(
                        f"variant {item.name:<42} [{(variant.label or 'Regular'):<10}] "
                        f"transfer ₹{to_decimal(variant.actual_price)} → ₹{new_transfer}  "
                        f"display ₹{to_decimal(variant.price)} → ₹{new_display}  "
                        f"MRP ₹{to_decimal(variant.original_price)} → ₹{new_mrp}"
                    )
                    variant.actual_price = new_transfer
                    variant.price = new_display
                    variant.original_price = new_mrp
                    updated_variants += 1

                first = live_variants[0]
                item.actual_price = first.actual_price
                item.price = first.price
                item.original_price = first.original_price
                updated_items += 1
                continue

            new_transfer, new_display, new_mrp = bump_prices(item.actual_price, item.price)
            print(
                f"item    {item.name:<42} "
                f"transfer ₹{to_decimal(item.actual_price)} → ₹{new_transfer}  "
                f"display ₹{to_decimal(item.price)} → ₹{new_display}  "
                f"MRP ₹{to_decimal(item.original_price)} → ₹{new_mrp}"
            )
            if new_transfer is not None:
                item.actual_price = new_transfer
            if new_display is not None:
                item.price = new_display
            item.original_price = new_mrp
            updated_items += 1

        if dry_run:
            db.rollback()
            print(
                f"DRY RUN: rolled back {updated_items} item(s), "
                f"{updated_variants} variant(s)."
            )
        else:
            db.commit()
            print(
                f"Done: {updated_items} item(s) updated, "
                f"{updated_variants} variant(s) updated."
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
        help="Print the new prices, then roll them back.",
    )
    args = parser.parse_args()
    update_prices(dry_run=args.dry_run)
