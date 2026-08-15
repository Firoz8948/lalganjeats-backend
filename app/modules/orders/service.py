# backend/app/modules/orders/service.py
from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import sms
from app.core.maps import estimate_customer_eta_minutes
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import PlaceOrderRequest
from app.modules.restaurants.models import Restaurant, MenuItem, MenuItemVariant
from app.modules.restaurants.service import _restaurant_visible_for_customer
from app.modules.users.models import Address, User
from app.modules.payments.service import ensure_payment_settings
from app.modules.payments.payment_split import calculate_split
from sqlalchemy.orm import joinedload
from app.modules.superadmin.models import Tenant


def _resolve_order_variant(db: Session, menu_item: MenuItem, variant_id: int | None):
    active = (
        db.query(MenuItemVariant)
        .filter(
            MenuItemVariant.menu_item_id == menu_item.id,
            MenuItemVariant.is_deleted == False,
            MenuItemVariant.is_available == True,
        )
        .order_by(MenuItemVariant.sort_order, MenuItemVariant.id)
        .all()
    )
    if variant_id is not None:
        match = next((v for v in active if v.id == variant_id), None)
        if not match:
            raise HTTPException(400, f"Variant {variant_id} unavailable for item {menu_item.id}")
        return match
    if len(active) == 1:
        return active[0]
    if len(active) == 0:
        # Legacy item without variants: synthesize pricing from parent
        return None
    raise HTTPException(
        400,
        f"Choose a size/variant for {menu_item.name}",
    )


def _next_order_number(db: Session) -> str:
    year = datetime.utcnow().year
    prefix = f"LE-{year}-"
    last = (
        db.query(Order)
        .filter(Order.order_number.like(f"{prefix}%"))
        .order_by(Order.id.desc())
        .first()
    )
    seq = 1
    if last and last.order_number:
        try:
            seq = int(last.order_number.split("-")[-1]) + 1
        except ValueError:
            seq = random.randint(1000, 9999)
    return f"{prefix}{seq:05d}"


def place_order(db: Session, customer: User, payload: PlaceOrderRequest) -> dict:
    if payload.payment_method not in ("cash", "online"):
        raise HTTPException(400, "payment_method must be cash or online")
    if not payload.items:
        raise HTTPException(400, "Cart is empty")

    restaurant = (
        db.query(Restaurant)
        .options(joinedload(Restaurant.tenant).joinedload(Tenant.zones))
        .filter(
            Restaurant.id == payload.restaurant_id,
            Restaurant.is_active == True,
            Restaurant.is_approved == True,
        )
        .first()
    )
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")
    if not restaurant.is_open:
        raise HTTPException(400, "Restaurant is closed")

    addr_text = payload.delivery_address
    lat = payload.delivery_latitude
    lng = payload.delivery_longitude
    if payload.address_id:
        addr = (
            db.query(Address)
            .filter(Address.id == payload.address_id, Address.user_id == customer.id)
            .first()
        )
        if not addr:
            raise HTTPException(404, "Address not found")
        parts = [addr.full_address]
        if addr.landmark:
            parts.append(addr.landmark)
        if addr.city:
            parts.append(addr.city)
        if addr.pincode:
            parts.append(addr.pincode)
        addr_text = ", ".join(parts)
        try:
            lat = float(addr.latitude) if addr.latitude else lat
            lng = float(addr.longitude) if addr.longitude else lng
        except (TypeError, ValueError):
            pass

    if not addr_text:
        raise HTTPException(400, "Delivery address is required")
    if lat is None or lng is None:
        raise HTTPException(
            400,
            "Delivery location coordinates are required to verify service area",
        )
    if not _restaurant_visible_for_customer(restaurant, float(lat), float(lng)):
        raise HTTPException(
            400,
            "This restaurant is outside your delivery area. Choose a closer location.",
        )

    display_total = 0.0
    actual_total = 0.0
    line_rows: list[tuple] = []
    for line in payload.items:
        mi = (
            db.query(MenuItem)
            .filter(
                MenuItem.id == line.menu_item_id,
                MenuItem.restaurant_id == restaurant.id,
                MenuItem.is_deleted == False,
                MenuItem.is_available == True,
            )
            .first()
        )
        if not mi:
            raise HTTPException(400, f"Menu item {line.menu_item_id} unavailable")
        variant = _resolve_order_variant(db, mi, line.variant_id)
        if variant is not None:
            display_price = float(variant.price)
            actual_price = float(variant.actual_price)
            variant_id = variant.id
            variant_label = variant.label
        else:
            display_price = float(mi.price)
            actual_price = float(mi.actual_price if mi.actual_price is not None else mi.price)
            variant_id = None
            variant_label = None
        sub = round(display_price * line.quantity, 2)
        display_total += sub
        actual_total += round(actual_price * line.quantity, 2)
        line_rows.append(
            (mi, display_price, actual_price, line.quantity, sub, variant_id, variant_label)
        )

    display_total = round(display_total, 2)
    actual_total = round(actual_total, 2)

    pay_settings = ensure_payment_settings(db)
    split = calculate_split(display_total, actual_total, pay_settings, display_total)

    discount = 0.0
    promo_code = None
    promo_percent = None
    promo_free_delivery = False
    promo_id = None

    customer_pays = round(max(0.0, split.customer_pays - discount), 2)

    distance_km = None
    eta_minutes = None
    r_lat = float(restaurant.latitude) if restaurant.latitude is not None else None
    r_lng = float(restaurant.longitude) if restaurant.longitude is not None else None
    if r_lat is not None and r_lng is not None and lat is not None and lng is not None:
        distance_km, eta_minutes = estimate_customer_eta_minutes(r_lat, r_lng, lat, lng)

    payment_status = "pending"
    online_stub = None
    if payload.payment_method == "online":
        payment_status = "paid"
        online_stub = {
            "stub": True,
            "message": "Online payment stub — treated as paid for development",
            "provider": "stub",
        }

    order = Order(
        order_number=_next_order_number(db),
        tenant_id=restaurant.tenant_id,
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        status="pending",
        payment_method=payload.payment_method,
        payment_status=payment_status,
        subtotal=Decimal(str(display_total)),
        delivery_fee=Decimal(str(split.delivery_charge)),
        discount=Decimal(str(discount)),
        total_amount=Decimal(str(customer_pays)),
        display_total=Decimal(str(display_total)),
        actual_total=Decimal(str(actual_total)),
        platform_fee=Decimal(str(split.platform_fee)),
        admin_earning=Decimal(str(split.admin_earning)),
        delivery_partner_earning=Decimal(str(split.delivery_earning)),
        delivery_address=addr_text,
        delivery_latitude=lat,
        delivery_longitude=lng,
        distance_km=distance_km,
        eta_minutes=eta_minutes,
        notes=payload.notes,
        promo_code_id=promo_id,
        promo_code=promo_code,
        promo_percent_off=promo_percent,
        promo_free_delivery=promo_free_delivery,
    )
    db.add(order)
    db.flush()

    for mi, d_price, a_price, qty, sub, variant_id, variant_label in line_rows:
        db.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=mi.id,
                variant_id=variant_id,
                name=mi.name,
                variant_label=variant_label,
                price=Decimal(str(d_price)),
                display_price=Decimal(str(d_price)),
                actual_price=Decimal(str(a_price)),
                quantity=qty,
                subtotal=Decimal(str(sub)),
            )
        )
    db.commit()
    db.refresh(order)

    hotel_phone = restaurant.phone or (
        restaurant.owner.phone if getattr(restaurant, "owner", None) else None
    )
    if hotel_phone:
        sms.send_order_alert(hotel_phone, order.order_number)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "delivery_fee": float(order.delivery_fee or 0),
        "discount": float(order.discount or 0),
        "distance_km": float(order.distance_km) if order.distance_km is not None else None,
        "eta_minutes": order.eta_minutes,
        "online_payment_stub": online_stub,
    }
