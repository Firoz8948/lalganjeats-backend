# backend/app/modules/promocodes/service.py
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.modules.promocodes.models import PromoCode, PromoCodeUsage
from app.modules.promocodes import repository as repo
from app.modules.promocodes.schemas import (
    PromoCreateRequest,
    PromoUpdateRequest,
    PromoOut,
    PromoValidateRequest,
    PromoValidateResponse,
    PromoUsageOut,
    PromoUsageItemOut,
)
from app.modules.orders.models import Order
from app.modules.users.models import User

MOBILE_CHANNELS = {"android_app", "ios_app"}
MSG_ONE_TIME = "APPLICABLE FOR ONE TIME ONLY"
MSG_NEW_USERS = "APPLICABLE FOR NEW USERS"
MSG_DEVICE_USED = "This mobile has already used this coupon code"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(promo: PromoCode) -> bool:
    if not promo.is_active:
        return True
    if promo.max_uses > 0 and promo.remaining_uses <= 0:
        return True
    if promo.expires_at is not None:
        exp = promo.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= _now():
            return True
    return False


def _maybe_auto_deactivate(db: Session, promo: PromoCode) -> None:
    """Mark inactive when uses exhausted or past expiry."""
    changed = False
    if promo.max_uses > 0 and promo.remaining_uses <= 0 and promo.is_active:
        promo.is_active = False
        promo.remaining_uses = 0
        changed = True
    if promo.expires_at is not None:
        exp = promo.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= _now() and promo.is_active:
            promo.is_active = False
            changed = True
    if changed:
        db.flush()


def _audience(promo: PromoCode) -> str:
    raw = (getattr(promo, "audience", None) or "all").strip().lower()
    return raw if raw in ("all", "new_users") else "all"


def _phone_digits(phone: str | None) -> str:
    return "".join(c for c in str(phone or "") if c.isdigit())[-10:]


def _normalize_device_id(raw: str | None) -> str | None:
    value = "".join(c for c in str(raw or "") if c.isalnum() or c in "-_")
    if len(value) < 8 or len(value) > 64:
        return None
    return value


def _device_used_new_user_coupon(
    db: Session,
    device_id: str | None,
    *,
    exclude_order_id: int | None = None,
) -> bool:
    normalized = _normalize_device_id(device_id)
    if not normalized:
        return False
    return repo.device_used_new_user_promo(
        db, normalized, exclude_order_id=exclude_order_id
    )


def _has_used_promo(
    db: Session,
    promo: PromoCode,
    *,
    user: User | None,
    exclude_order_id: int | None = None,
) -> bool:
    phone = _phone_digits(user.phone if user else None)
    user_id = user.id if user else None
    usage = repo.list_usages_for_phone(db, promo.id, phone, user_id=user_id)
    if usage and usage.order_id != exclude_order_id:
        return True
    return False


def _is_new_customer(
    db: Session,
    user: User,
    *,
    exclude_order_id: int | None = None,
) -> bool:
    q = db.query(Order.id).filter(
        Order.customer_id == user.id,
        Order.status != "cancelled",
    )
    if exclude_order_id is not None:
        q = q.filter(Order.id != exclude_order_id)
    return q.first() is None


def _eligibility_error(
    db: Session,
    promo: PromoCode,
    user: User | None,
    *,
    exclude_order_id: int | None = None,
    device_id: str | None = None,
) -> PromoValidateResponse | None:
    """One-time per mobile/account, new-user gate, and one new-user code per device."""
    if user is not None and _has_used_promo(
        db, promo, user=user, exclude_order_id=exclude_order_id
    ):
        return PromoValidateResponse(
            valid=False,
            reason="one_time",
            message=MSG_ONE_TIME,
            code=promo.code,
            channel=promo.channel,
        )
    if _audience(promo) == "new_users":
        if _device_used_new_user_coupon(
            db, device_id, exclude_order_id=exclude_order_id
        ):
            return PromoValidateResponse(
                valid=False,
                reason="device_used",
                message=MSG_DEVICE_USED,
                code=promo.code,
                channel=promo.channel,
            )
        if user is not None and not _is_new_customer(
            db, user, exclude_order_id=exclude_order_id
        ):
            return PromoValidateResponse(
                valid=False,
                reason="new_users",
                message=MSG_NEW_USERS,
                code=promo.code,
                channel=promo.channel,
            )
    return None


def _discount_type(promo: PromoCode) -> str:
    raw = (getattr(promo, "discount_type", None) or "percent").strip().lower()
    return raw if raw in ("percent", "flat") else "percent"


def _compute_discount(promo: PromoCode, subtotal: Decimal | None) -> Decimal:
    if subtotal is None:
        return Decimal("0")
    dtype = _discount_type(promo)
    if dtype == "flat":
        flat = Decimal(str(promo.flat_off or 0))
        if flat <= 0:
            return Decimal("0")
        return min(flat, subtotal).quantize(Decimal("0.01"))
    if promo.percent_off:
        return (
            subtotal * Decimal(str(promo.percent_off)) / Decimal("100")
        ).quantize(Decimal("0.01"))
    return Decimal("0")


def _format_rupees(amount: Decimal | float | int) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    if value == value.to_integral():
        return str(int(value))
    return f"{value:.2f}"


def _to_out(promo: PromoCode) -> PromoOut:
    if promo.max_uses == 0:
        used = 0  # unlimited — count from usages if needed later
    else:
        used = max(0, (promo.max_uses or 0) - (promo.remaining_uses or 0))
    return PromoOut(
        id=promo.id,
        code=promo.code,
        channel=promo.channel,
        audience=_audience(promo),
        discount_type=_discount_type(promo),
        percent_off=promo.percent_off,
        flat_off=getattr(promo, "flat_off", None),
        min_cart_value=getattr(promo, "min_cart_value", None),
        free_delivery=bool(promo.free_delivery),
        expires_at=promo.expires_at,
        max_uses=promo.max_uses,
        remaining_uses=promo.remaining_uses,
        used_count=used,
        is_active=bool(promo.is_active),
        is_public=bool(getattr(promo, "is_public", False)),
        is_expired=_is_expired(promo),
        description=promo.description,
        created_at=promo.created_at,
    )


def list_promos(db: Session, tenant_id: int | None) -> list[PromoOut]:
    items = []
    for p in repo.list_promos(db, tenant_id):
        _maybe_auto_deactivate(db, p)
        items.append(_to_out(p))
    db.commit()
    return items


def list_public_active_promos(
    db: Session,
    tenant_id: int | None = None,
    current_user: User | None = None,
    device_id: str | None = None,
) -> list[dict]:
    rows = []
    for promo in repo.list_public_active(db, tenant_id):
        _maybe_auto_deactivate(db, promo)
        if _is_expired(promo) or not promo.is_active:
            continue
        if _eligibility_error(db, promo, current_user, device_id=device_id):
            continue
        rows.append(
            {
                "code": promo.code,
                "channel": promo.channel,
                "discount_type": _discount_type(promo),
                "percent_off": float(promo.percent_off) if promo.percent_off is not None else None,
                "flat_off": float(promo.flat_off) if getattr(promo, "flat_off", None) is not None else None,
                "min_cart_value": (
                    float(promo.min_cart_value)
                    if getattr(promo, "min_cart_value", None) is not None
                    else None
                ),
                "free_delivery": bool(promo.free_delivery),
                "description": promo.description,
                "expires_at": promo.expires_at.isoformat() if promo.expires_at else None,
            }
        )
    db.commit()
    return rows


def create_promo(
    db: Session, tenant_id: int | None, payload: PromoCreateRequest
) -> PromoOut:
    existing = repo.get_by_code(db, payload.code, tenant_id)
    if existing:
        raise HTTPException(400, detail="Promocode already exists")

    promo = PromoCode(
        tenant_id=tenant_id,
        code=payload.code,
        channel=payload.channel,
        audience=payload.audience,
        discount_type=payload.discount_type,
        percent_off=payload.percent_off,
        flat_off=payload.flat_off,
        min_cart_value=payload.min_cart_value,
        free_delivery=payload.free_delivery,
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
        remaining_uses=payload.max_uses,
        is_active=True,
        is_public=bool(payload.is_public),
        description=payload.description,
    )
    repo.create(db, promo)
    db.commit()
    db.refresh(promo)
    return _to_out(promo)


def update_promo(
    db: Session,
    tenant_id: int | None,
    promo_id: int,
    payload: PromoUpdateRequest,
) -> PromoOut:
    promo = repo.get_by_id(db, promo_id, tenant_id)
    if not promo:
        raise HTTPException(404, detail="Promocode not found")

    data = payload.model_dump(exclude_unset=True)
    if "max_uses" in data:
        new_max = data["max_uses"]
        if new_max == 0:
            promo.max_uses = 0
            promo.remaining_uses = 0
        elif promo.max_uses == 0:
            # was unlimited → now capped
            promo.max_uses = new_max
            promo.remaining_uses = new_max
        else:
            used = max(0, promo.max_uses - promo.remaining_uses)
            if new_max < used:
                raise HTTPException(
                    400,
                    detail=f"max_uses cannot be less than already used ({used})",
                )
            promo.max_uses = new_max
            promo.remaining_uses = new_max - used
            if promo.remaining_uses <= 0:
                promo.is_active = False
        del data["max_uses"]

    for key, value in data.items():
        setattr(promo, key, value)

    _maybe_auto_deactivate(db, promo)
    db.commit()
    db.refresh(promo)
    return _to_out(promo)


def delete_promo(db: Session, tenant_id: int | None, promo_id: int) -> dict:
    promo = repo.get_by_id(db, promo_id, tenant_id)
    if not promo:
        raise HTTPException(404, detail="Promocode not found")
    db.delete(promo)
    db.commit()
    return {"message": "Promocode deleted"}


def validate_promo(
    db: Session,
    payload: PromoValidateRequest,
    tenant_id: int | None = None,
    current_user: User | None = None,
    exclude_order_id: int | None = None,
    device_id: str | None = None,
) -> PromoValidateResponse:
    promo = repo.get_by_code(db, payload.code, tenant_id)
    if not promo:
        # Fallback: try global lookup if tenant-scoped miss
        if tenant_id is not None:
            promo = repo.get_by_code(db, payload.code, None)
    if not promo:
        return PromoValidateResponse(
            valid=False,
            reason="not_found",
            message="Invalid promocode",
        )

    _maybe_auto_deactivate(db, promo)
    db.commit()

    if promo.channel == "mobile_app" and payload.client_channel == "web":
        return PromoValidateResponse(
            valid=False,
            reason="mobile_app_only",
            message="Promocode applicable for mobile app only. Download now.",
            download_required=True,
            code=promo.code,
            channel=promo.channel,
        )

    if promo.channel == "mobile_app" and payload.client_channel not in MOBILE_CHANNELS:
        return PromoValidateResponse(
            valid=False,
            reason="mobile_app_only",
            message="Promocode applicable for mobile app only. Download now.",
            download_required=True,
            code=promo.code,
            channel=promo.channel,
        )

    if _is_expired(promo):
        return PromoValidateResponse(
            valid=False,
            reason="expired",
            message="This promocode has expired",
            code=promo.code,
        )

    if not promo.is_active:
        return PromoValidateResponse(
            valid=False,
            reason="inactive",
            message="This promocode is no longer active",
            code=promo.code,
        )

    blocked = _eligibility_error(
        db,
        promo,
        current_user,
        exclude_order_id=exclude_order_id,
        device_id=device_id or getattr(payload, "device_id", None),
    )
    if blocked:
        return blocked

    min_cart = getattr(promo, "min_cart_value", None)
    if (
        min_cart is not None
        and Decimal(str(min_cart)) > 0
        and payload.subtotal is not None
        and Decimal(str(payload.subtotal)) < Decimal(str(min_cart))
    ):
        amount = _format_rupees(min_cart)
        return PromoValidateResponse(
            valid=False,
            reason="min_cart",
            message=f"Order applicable above {amount} Rs",
            code=promo.code,
            channel=promo.channel,
            discount_type=_discount_type(promo),
            percent_off=promo.percent_off,
            flat_off=getattr(promo, "flat_off", None),
            min_cart_value=promo.min_cart_value,
            free_delivery=bool(promo.free_delivery),
        )

    discount = _compute_discount(promo, payload.subtotal)
    delivery_after = payload.delivery_fee
    if promo.free_delivery and payload.delivery_fee is not None:
        delivery_after = Decimal("0")

    return PromoValidateResponse(
        valid=True,
        message="Promocode applied",
        code=promo.code,
        channel=promo.channel,
        discount_type=_discount_type(promo),
        percent_off=promo.percent_off,
        flat_off=getattr(promo, "flat_off", None),
        min_cart_value=getattr(promo, "min_cart_value", None),
        free_delivery=bool(promo.free_delivery),
        discount_amount=discount,
        delivery_fee_after=delivery_after,
        remaining_uses=promo.remaining_uses,
    )


def apply_promo_to_order(
    db: Session,
    *,
    order: Order,
    code: str,
    client_channel: str,
    tenant_id: int | None = None,
    device_id: str | None = None,
) -> PromoValidateResponse:
    """
    Call when an order is placed. Validates, writes order snapshot,
    creates usage row, decrements remaining_uses.
    """
    payload = PromoValidateRequest(
        code=code,
        client_channel=client_channel,  # type: ignore[arg-type]
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        device_id=device_id,
    )
    customer = order.customer
    if customer is None and order.customer_id:
        customer = db.query(User).filter(User.id == order.customer_id).first()
    result = validate_promo(
        db,
        payload,
        tenant_id=tenant_id,
        current_user=customer,
        exclude_order_id=order.id,
        device_id=device_id,
    )
    if not result.valid:
        return result

    promo = repo.get_by_code(db, code, tenant_id) or repo.get_by_code(db, code, None)
    if not promo:
        return result

    # Prevent double-apply
    if order.promo_code_id:
        raise HTTPException(400, detail="Order already has a promocode")

    discount = result.discount_amount or Decimal("0")
    free_del = bool(promo.free_delivery)

    order.promo_code_id = promo.id
    order.promo_code = promo.code
    order.promo_percent_off = promo.percent_off
    order.promo_discount_type = _discount_type(promo)
    order.promo_flat_off = getattr(promo, "flat_off", None)
    order.promo_free_delivery = free_del
    order.discount = discount
    if free_del:
        order.delivery_fee = Decimal("0")

    # Recalc total via payments.breakdown (single source of truth)
    try:
        from decimal import Decimal as D

        from app.modules.payments.breakdown import (
            breakdown_from_order,
            customer_price_view,
        )

        display = float(order.display_total or order.subtotal or 0)
        cv = customer_price_view(
            display_price=display,
            platform_fee=float(order.platform_fee or 0),
            delivery_charge=float(order.delivery_fee or 0),
            discount=float(discount),
        )
        order.total_amount = D(str(cv.customer_total))
        order.admin_earning = D(
            str(breakdown_from_order(order).admin.admin_profit)
        )
    except Exception:
        pass

    usage = PromoCodeUsage(
        promo_code_id=promo.id,
        order_id=order.id,
        user_id=order.customer_id,
        customer_phone=_phone_digits(customer.phone if customer else None),
        device_id=_normalize_device_id(device_id),
        discount_amount=discount,
        percent_off_snapshot=promo.percent_off,
        discount_type_snapshot=_discount_type(promo),
        flat_off_snapshot=getattr(promo, "flat_off", None),
        free_delivery_applied=free_del,
        client_channel=client_channel,
    )
    db.add(usage)

    if promo.max_uses > 0:
        promo.remaining_uses = max(0, promo.remaining_uses - 1)
        if promo.remaining_uses <= 0:
            promo.is_active = False
            promo.remaining_uses = 0

    db.flush()
    return result


def get_usages(
    db: Session, tenant_id: int | None, promo_id: int
) -> list[PromoUsageOut]:
    promo = repo.get_by_id(db, promo_id, tenant_id)
    if not promo:
        raise HTTPException(404, detail="Promocode not found")

    rows = []
    for u in repo.list_usages(db, promo_id):
        order = u.order
        if not order:
            continue
        items = [
            PromoUsageItemOut(
                name=i.name,
                quantity=i.quantity,
                price=i.price,
                subtotal=i.subtotal,
            )
            for i in (order.items or [])
        ]
        customer = u.user
        rows.append(
            PromoUsageOut(
                id=u.id,
                order_id=order.id,
                order_number=order.order_number,
                customer_name=customer.full_name if customer else None,
                customer_phone=customer.phone if customer else None,
                restaurant_name=order.restaurant.name if order.restaurant else None,
                discount_amount=u.discount_amount,
                percent_off_snapshot=u.percent_off_snapshot,
                discount_type_snapshot=getattr(u, "discount_type_snapshot", None),
                flat_off_snapshot=getattr(u, "flat_off_snapshot", None),
                free_delivery_applied=bool(u.free_delivery_applied),
                client_channel=u.client_channel,
                created_at=u.created_at,
                items=items,
            )
        )
    return rows
