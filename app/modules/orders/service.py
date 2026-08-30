# backend/app/modules/orders/service.py
from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import sms
from app.core.maps import estimate_customer_eta_minutes, haversine_km
from app.modules.orders.models import Order, OrderItem
from app.modules.orders.schemas import PlaceOrderRequest
from app.modules.restaurants.models import Restaurant, MenuItem, MenuItemVariant
from app.modules.restaurants.service import _restaurant_visible_for_customer
from app.modules.restaurants.service_area import (
    delivery_charge_for_distance,
    matching_delivery_exception,
)
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


def validate_payment_method(
    payment_method: str,
    order_total: float,
    settings,
) -> None:
    if payment_method == "online":
        if not bool(getattr(settings, "allow_prepaid_orders", True)):
            raise HTTPException(400, "Prepaid orders are currently disabled")
        return
    if payment_method != "cash":
        raise HTTPException(400, "payment_method must be cash or online")
    if not bool(getattr(settings, "allow_cod_orders", True)):
        raise HTTPException(400, "Cash on delivery is currently disabled")
    threshold = float(getattr(settings, "cod_max_order_amount", 500) or 0)
    if float(order_total) >= threshold:
        raise HTTPException(
            400,
            f"Cash on delivery is available only below ₹{threshold:g}. "
            "Please choose prepaid payment.",
        )


def place_order(db: Session, customer: User, payload: PlaceOrderRequest) -> dict:
    if payload.payment_method not in ("cash", "online"):
        raise HTTPException(400, "payment_method must be cash or online")
    if not payload.items:
        raise HTTPException(400, "Cart is empty")

    restaurant = (
        db.query(Restaurant)
        .options(
            joinedload(Restaurant.tenant).joinedload(Tenant.zones),
            joinedload(Restaurant.tenant).joinedload(Tenant.delivery_exceptions),
        )
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
            # The explicitly chosen map/GPS point is authoritative. Saved
            # address coordinates are only a fallback for older clients.
            if lat is None and addr.latitude is not None:
                lat = float(addr.latitude)
            if lng is None and addr.longitude is not None:
                lng = float(addr.longitude)
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

    tenant = restaurant.tenant
    exception = matching_delivery_exception(
        tenant.delivery_exceptions or [],
        float(lat),
        float(lng),
    )
    if exception is not None:
        zone_delivery_charge = float(exception.delivery_charge)
    else:
        zone_origin_lat = (
            float(restaurant.latitude)
            if restaurant.latitude is not None
            else float(tenant.center_latitude)
        )
        zone_origin_lng = (
            float(restaurant.longitude)
            if restaurant.longitude is not None
            else float(tenant.center_longitude)
        )
        zone_distance_km = haversine_km(
            float(lat),
            float(lng),
            zone_origin_lat,
            zone_origin_lng,
        )
        zone_delivery_charge = delivery_charge_for_distance(
            tenant.zones or [],
            zone_distance_km,
        )
    if zone_delivery_charge is None:
        raise HTTPException(
            400,
            "No active delivery zone covers this location.",
        )

    pay_settings = ensure_payment_settings(db)
    split = calculate_split(
        display_total,
        actual_total,
        pay_settings,
        delivery_charge=zone_delivery_charge,
    )

    discount = 0.0
    promo_code = None
    promo_percent = None
    promo_free_delivery = False
    promo_id = None

    customer_pays = round(max(0.0, split.customer_pays - discount), 2)
    validate_payment_method(payload.payment_method, customer_pays, pay_settings)

    distance_km = None
    eta_minutes = None
    r_lat = float(restaurant.latitude) if restaurant.latitude is not None else None
    r_lng = float(restaurant.longitude) if restaurant.longitude is not None else None
    if r_lat is not None and r_lng is not None and lat is not None and lng is not None:
        distance_km, eta_minutes = estimate_customer_eta_minutes(r_lat, r_lng, lat, lng)

    payment_status = "pending"
    if payload.payment_method == "online":
        from app.core.payu_service import payu_configured
        if not payu_configured():
            raise HTTPException(
                503,
                "Online payments are not configured. Please use cash on delivery.",
            )

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
        # Store fixed checkout platform charge (₹), not legacy %.
        platform_fee=Decimal(str(split.platform_charge)),
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

    if payload.promo_code:
        from app.modules.promocodes.service import apply_promo_to_order

        promo_result = apply_promo_to_order(
            db,
            order=order,
            code=payload.promo_code,
            client_channel=getattr(payload, "client_channel", None) or "web",
            tenant_id=restaurant.tenant_id,
        )
        if not promo_result.valid:
            db.rollback()
            detail = {
                "reason": promo_result.reason,
                "message": promo_result.message,
                "download_required": bool(promo_result.download_required),
            }
            raise HTTPException(400, detail=detail)

        # Discount is absorbed by admin; refresh P/L from canonical breakdown.
        from app.modules.payments.breakdown import breakdown_from_order

        bd = breakdown_from_order(order)
        order.total_amount = Decimal(str(bd.customer.customer_total))
        order.admin_earning = Decimal(str(bd.admin.admin_profit))

    db.commit()
    db.refresh(order)

    # Notify hotel only when payment is already settled (COD) or not required.
    if order.payment_method != "online" or order.payment_status == "paid":
        hotel_phone = restaurant.phone or (
            restaurant.owner.phone if getattr(restaurant, "owner", None) else None
        )
        if hotel_phone:
            sms.send_order_alert(hotel_phone, order.order_number)

        # Send FCM background push to restaurant owner
        if getattr(restaurant, "owner", None) and getattr(restaurant.owner, "fcm_token", None):
            try:
                from app.core.fcm import send_push_notification
                send_push_notification(
                    restaurant.owner.fcm_token,
                    "🎉 New Order Received!",
                    f"You received a new order #{order.order_number}. Accept now and cook it!",
                    {"order_id": str(order.id), "type": "new_order"},
                )
            except Exception:
                pass

        # SMS alert to admin phone numbers on every new order
        for admin_phone in ("9670517135", "9721054930"):
            try:
                sms.send_order_alert(admin_phone, order.order_number)
            except Exception:
                pass

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "delivery_fee": float(order.delivery_fee or 0),
        "discount": float(order.discount or 0),
        "platform_charge": float(order.platform_fee or 0),
        "distance_km": float(order.distance_km) if order.distance_km is not None else None,
        "eta_minutes": order.eta_minutes,
        "needs_payment": order.payment_method == "online" and order.payment_status != "paid",
    }
