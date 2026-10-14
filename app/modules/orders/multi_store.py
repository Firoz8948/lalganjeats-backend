# backend/app/modules/orders/multi_store.py
"""Grocery-only orders that span several stores.

One parent order carries everything the customer and rider see (payment,
delivery fee priced from the tenant's locked centre, platform charge, promo,
OTP, doorstep collection). Each store gets a sub-order (LE-YYYY-NNNNN(a), (b)…)
holding only its items and its transfer amount.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.maps import COOK_BUFFER_MIN, drive_minutes_for_km
from app.modules.orders.models import Order
from app.modules.orders.numbering import sub_order_number
from app.modules.orders.schemas import PlaceMultiStoreOrderRequest
from app.modules.orders.service import (
    _next_order_number,
    add_order_items,
    apply_customer_name,
    build_line_rows,
    resolve_delivery_point,
    validate_payment_method,
)
from app.modules.payments.breakdown import packing_charge_for_restaurant
from app.modules.payments.payment_split import SplitResult, calculate_split
from app.modules.payments.service import ensure_payment_settings
from app.modules.restaurants.models import CatalogCategory, Restaurant
from app.modules.restaurants.service import (
    _restaurant_visible_for_customer,
    tenant_road_km_to_customer,
)
from app.modules.restaurants.service_area import (
    delivery_rates_for_distance,
    matching_delivery_exception,
    max_active_zone_radius_km,
)
from app.modules.superadmin.models import Tenant
from app.modules.users.models import User

GROCERY_SLUG = "grocery"
# Extra minutes per additional store the rider has to stop at.
PICKUP_BUFFER_MIN_PER_STORE = 5


@dataclass
class StoreCart:
    restaurant: Restaurant
    line_rows: list[tuple]
    display_total: float
    actual_total: float
    packing_charge: float

    @property
    def item_count(self) -> int:
        return sum(int(row[3]) for row in self.line_rows)


@dataclass
class MultiStorePlan:
    tenant: Tenant
    category_id: int
    addr_text: str
    lat: float
    lng: float
    distance_km: float | None
    eta_minutes: int | None
    split: SplitResult
    display_total: float
    actual_total: float
    packing_total: float
    stores: list[StoreCart] = field(default_factory=list)


def ensure_enabled() -> None:
    if not settings.MULTI_STORE_ORDERS_ENABLED:
        raise HTTPException(404, "Ordering from several stores is not available yet")


def grocery_category_id(db: Session) -> int:
    row = (
        db.query(CatalogCategory.id)
        .filter(func.lower(CatalogCategory.slug) == GROCERY_SLUG)
        .first()
    )
    if not row:
        raise HTTPException(503, "Grocery category is not configured")
    return int(row[0])


def _load_stores(db: Session, payload: PlaceMultiStoreOrderRequest, category_id: int) -> list[Restaurant]:
    ids = [s.restaurant_id for s in payload.stores]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "Each store can appear only once in the cart")
    max_stores = max(2, int(settings.MULTI_STORE_MAX_STORES or 2))
    if len(ids) > max_stores:
        raise HTTPException(400, f"You can order from at most {max_stores} stores at once")

    rows = (
        db.query(Restaurant)
        .options(
            joinedload(Restaurant.tenant).joinedload(Tenant.zones),
            joinedload(Restaurant.tenant).joinedload(Tenant.delivery_exceptions),
        )
        .filter(
            Restaurant.id.in_(ids),
            Restaurant.is_active == True,
            Restaurant.is_approved == True,
        )
        .all()
    )
    by_id = {r.id: r for r in rows}
    stores: list[Restaurant] = []
    for rid in ids:
        restaurant = by_id.get(rid)
        if restaurant is None:
            raise HTTPException(404, f"Store {rid} not found")
        if restaurant.business_category_id != category_id:
            raise HTTPException(
                400,
                f"{restaurant.name} is not a grocery store. "
                "Only grocery stores can be combined in one order.",
            )
        if not restaurant.is_open:
            raise HTTPException(400, f"{restaurant.name} is closed right now")
        stores.append(restaurant)

    tenant_ids = {r.tenant_id for r in stores}
    if len(tenant_ids) != 1 or None in tenant_ids:
        raise HTTPException(400, "These stores can't be combined in one order")
    return stores


def _delivery_rates(tenant: Tenant, lat: float, lng: float) -> tuple[float, float, float | None]:
    """(customer delivery charge, rider payout, km from tenant centre)."""
    centre_km = tenant_road_km_to_customer(tenant, lat, lng)
    exception = matching_delivery_exception(tenant.delivery_exceptions or [], lat, lng)
    if exception is not None:
        charge = float(exception.delivery_charge)
        return charge, charge, centre_km

    rates = (
        delivery_rates_for_distance(tenant.zones or [], centre_km)
        if centre_km is not None
        else None
    )
    if rates is None:
        max_km = max_active_zone_radius_km(tenant.zones or []) or 10.0
        raise HTTPException(
            400,
            f"Orders not available as your position is outside {max_km:g} km distance of Lalganj Ajhara. Contact on Insta @lalganjeats to unlock your location",
        )
    charge, payout, _ = rates
    return float(charge), float(payout), centre_km


def build_plan(
    db: Session, customer: User, payload: PlaceMultiStoreOrderRequest
) -> MultiStorePlan:
    category_id = grocery_category_id(db)
    restaurants = _load_stores(db, payload, category_id)

    addr_text, lat, lng = resolve_delivery_point(
        db,
        customer,
        address_id=payload.address_id,
        delivery_address=payload.delivery_address,
        lat=payload.delivery_latitude,
        lng=payload.delivery_longitude,
    )
    for restaurant in restaurants:
        if not _restaurant_visible_for_customer(restaurant, lat, lng):
            raise HTTPException(
                400,
                f"{restaurant.name} does not deliver to this location. Choose a closer location.",
            )

    items_by_store = {s.restaurant_id: s.items for s in payload.stores}
    stores: list[StoreCart] = []
    for restaurant in restaurants:
        rows, display, actual = build_line_rows(db, restaurant, items_by_store[restaurant.id])
        stores.append(
            StoreCart(
                restaurant=restaurant,
                line_rows=rows,
                display_total=display,
                actual_total=actual,
                packing_charge=packing_charge_for_restaurant(restaurant),
            )
        )

    tenant = restaurants[0].tenant
    delivery_charge, dp_payout, centre_km = _delivery_rates(tenant, lat, lng)

    eta_minutes = None
    if centre_km is not None:
        eta_minutes = (
            COOK_BUFFER_MIN
            + drive_minutes_for_km(centre_km)
            + PICKUP_BUFFER_MIN_PER_STORE * (len(stores) - 1)
        )

    display_total = round(sum(s.display_total for s in stores), 2)
    actual_total = round(sum(s.actual_total for s in stores), 2)
    packing_total = round(sum(s.packing_charge for s in stores), 2)
    split = calculate_split(
        display_total,
        actual_total,
        ensure_payment_settings(db),
        delivery_charge=delivery_charge,
        delivery_payout=dp_payout,
        packing_charge=packing_total,
    )

    return MultiStorePlan(
        tenant=tenant,
        category_id=category_id,
        addr_text=addr_text,
        lat=lat,
        lng=lng,
        distance_km=centre_km,
        eta_minutes=eta_minutes,
        split=split,
        display_total=display_total,
        actual_total=actual_total,
        packing_total=packing_total,
        stores=stores,
    )


def _store_summary(store: StoreCart, sub: Order | None = None) -> dict:
    return {
        "restaurant_id": store.restaurant.id,
        "restaurant_name": store.restaurant.name,
        "order_id": sub.id if sub is not None else None,
        "order_number": sub.order_number if sub is not None else None,
        "item_count": store.item_count,
        "subtotal": store.display_total,
        "packing_charge": store.packing_charge,
    }


def quote_multi_store_order(
    db: Session, customer: User, payload: PlaceMultiStoreOrderRequest
) -> dict:
    ensure_enabled()
    plan = build_plan(db, customer, payload)
    split = plan.split
    return {
        "subtotal": plan.display_total,
        "delivery_fee": split.delivery_charge,
        "platform_charge": split.platform_charge,
        "packing_charge": plan.packing_total,
        "discount": 0.0,
        "total_amount": split.customer_pays,
        "distance_km": plan.distance_km,
        "eta_minutes": plan.eta_minutes,
        "stores": [_store_summary(s) for s in plan.stores],
    }


def _promo_precheck(
    db: Session, customer: User, payload: PlaceMultiStoreOrderRequest, plan: MultiStorePlan
) -> None:
    code = (payload.promo_code or "").strip()
    if not code:
        return
    from app.modules.promocodes.schemas import PromoValidateRequest
    from app.modules.promocodes.service import validate_promo

    precheck = validate_promo(
        db,
        PromoValidateRequest(
            code=code,
            client_channel=payload.client_channel or "web",
            subtotal=Decimal(str(plan.display_total)),
            delivery_fee=Decimal(str(plan.split.delivery_charge)),
            device_id=payload.device_id,
            restaurant_id=None,
        ),
        tenant_id=plan.tenant.id,
        current_user=customer,
        device_id=payload.device_id,
        category_id=plan.category_id,
    )
    if not precheck.valid:
        raise HTTPException(
            400,
            detail={
                "reason": precheck.reason,
                "message": precheck.message,
                "download_required": bool(precheck.download_required),
                "min_cart_value": (
                    float(precheck.min_cart_value)
                    if precheck.min_cart_value is not None
                    else None
                ),
            },
        )


def place_multi_store_order(
    db: Session, customer: User, payload: PlaceMultiStoreOrderRequest
) -> dict:
    ensure_enabled()
    if payload.payment_method not in ("cash", "online"):
        raise HTTPException(400, "payment_method must be cash or online")

    apply_customer_name(db, customer, payload.customer_name)
    plan = build_plan(db, customer, payload)
    split = plan.split

    pay_settings = ensure_payment_settings(db)
    validate_payment_method(payload.payment_method, split.customer_pays, pay_settings)
    if payload.payment_method == "online":
        from app.core.razorpay_service import razorpay_configured

        if not razorpay_configured():
            raise HTTPException(
                503,
                "Online payments are not configured. Please use cash on delivery.",
            )

    _promo_precheck(db, customer, payload, plan)

    parent = Order(
        order_number=_next_order_number(db),
        tenant_id=plan.tenant.id,
        customer_id=customer.id,
        restaurant_id=None,
        is_multi_store=True,
        status="pending",
        payment_method=payload.payment_method,
        payment_status="pending",
        subtotal=Decimal(str(plan.display_total)),
        delivery_fee=Decimal(str(split.delivery_charge)),
        discount=Decimal("0"),
        total_amount=Decimal(str(split.customer_pays)),
        display_total=Decimal(str(plan.display_total)),
        actual_total=Decimal(str(plan.actual_total)),
        packing_charge=Decimal(str(plan.packing_total)),
        platform_fee=Decimal(str(split.platform_charge)),
        admin_earning=Decimal(str(split.admin_earning)),
        delivery_partner_earning=Decimal(str(split.delivery_earning)),
        delivery_address=plan.addr_text,
        delivery_latitude=plan.lat,
        delivery_longitude=plan.lng,
        distance_km=plan.distance_km,
        eta_minutes=plan.eta_minutes,
        notes=payload.notes,
    )
    db.add(parent)
    db.flush()

    # Sub-orders hold goods only: fees, promo and the rider's payout stay on
    # the parent so nothing is counted twice.
    subs: list[Order] = []
    for index, store in enumerate(plan.stores):
        goods_total = round(store.display_total + store.packing_charge, 2)
        sub = Order(
            order_number=sub_order_number(parent.order_number, index),
            tenant_id=plan.tenant.id,
            customer_id=customer.id,
            restaurant_id=store.restaurant.id,
            parent_order_id=parent.id,
            status="pending",
            payment_method=payload.payment_method,
            payment_status="pending",
            subtotal=Decimal(str(store.display_total)),
            delivery_fee=Decimal("0"),
            discount=Decimal("0"),
            total_amount=Decimal(str(goods_total)),
            display_total=Decimal(str(store.display_total)),
            actual_total=Decimal(str(store.actual_total)),
            packing_charge=Decimal(str(store.packing_charge)),
            platform_fee=Decimal("0"),
            admin_earning=Decimal("0"),
            delivery_partner_earning=Decimal("0"),
            delivery_address=plan.addr_text,
            delivery_latitude=plan.lat,
            delivery_longitude=plan.lng,
            eta_minutes=plan.eta_minutes,
            notes=payload.notes,
        )
        db.add(sub)
        db.flush()
        add_order_items(db, sub, store.line_rows)
        subs.append(sub)

    if (payload.promo_code or "").strip():
        from app.modules.payments.breakdown import breakdown_from_order
        from app.modules.promocodes.service import apply_promo_to_order

        promo_result = apply_promo_to_order(
            db,
            order=parent,
            code=payload.promo_code,
            client_channel=payload.client_channel or "web",
            tenant_id=plan.tenant.id,
            device_id=payload.device_id,
            category_id=plan.category_id,
        )
        if not promo_result.valid:
            db.rollback()
            raise HTTPException(
                400,
                detail={
                    "reason": promo_result.reason,
                    "message": promo_result.message,
                    "download_required": bool(promo_result.download_required),
                },
            )
        bd = breakdown_from_order(parent)
        parent.total_amount = Decimal(str(bd.customer.customer_total))
        parent.admin_earning = Decimal(str(bd.admin.admin_profit))

    db.commit()
    db.refresh(parent)

    if payload.payment_method == "online":
        _fail_stale_prepaid(db, customer, own_ids=[parent.id, *(s.id for s in subs)])

    if parent.payment_method != "online":
        from app.core.order_alerts import notify_multi_store_order

        notify_multi_store_order(db, parent)

    return {
        "id": parent.id,
        "order_number": parent.order_number,
        "status": parent.status,
        "payment_method": parent.payment_method,
        "payment_status": parent.payment_status,
        "total_amount": float(parent.total_amount),
        "delivery_fee": float(parent.delivery_fee or 0),
        "discount": float(parent.discount or 0),
        "platform_charge": float(parent.platform_fee or 0),
        "packing_charge": float(parent.packing_charge or 0),
        "distance_km": float(parent.distance_km) if parent.distance_km is not None else None,
        "eta_minutes": parent.eta_minutes,
        "needs_payment": parent.payment_method == "online" and parent.payment_status != "paid",
        "is_multi_store": True,
        "stores": [_store_summary(store, sub) for store, sub in zip(plan.stores, subs)],
    }


def _fail_stale_prepaid(db: Session, customer: User, own_ids: list[int]) -> None:
    from app.modules.orders.payment_state import mark_prepaid_failed

    stale = (
        db.query(Order)
        .filter(
            Order.customer_id == customer.id,
            Order.id.notin_(own_ids),
            Order.payment_method == "online",
            Order.status == "pending",
            Order.payment_status.notin_(["paid", "failed"]),
        )
        .all()
    )
    changed = False
    for row in stale:
        if mark_prepaid_failed(row):
            changed = True
    if changed:
        db.commit()
