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

MOBILE_CHANNELS = {"android_app", "ios_app"}


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


def _to_out(promo: PromoCode) -> PromoOut:
    if promo.max_uses == 0:
        used = 0  # unlimited — count from usages if needed later
    else:
        used = max(0, (promo.max_uses or 0) - (promo.remaining_uses or 0))
    return PromoOut(
        id=promo.id,
        code=promo.code,
        channel=promo.channel,
        percent_off=promo.percent_off,
        free_delivery=bool(promo.free_delivery),
        expires_at=promo.expires_at,
        max_uses=promo.max_uses,
        remaining_uses=promo.remaining_uses,
        used_count=used,
        is_active=bool(promo.is_active),
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
        percent_off=payload.percent_off,
        free_delivery=payload.free_delivery,
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
        remaining_uses=payload.max_uses,
        is_active=True,
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

    discount = Decimal("0")
    delivery_after = payload.delivery_fee
    if promo.percent_off and payload.subtotal is not None:
        discount = (payload.subtotal * Decimal(promo.percent_off) / Decimal("100")).quantize(
            Decimal("0.01")
        )
    if promo.free_delivery and payload.delivery_fee is not None:
        delivery_after = Decimal("0")

    return PromoValidateResponse(
        valid=True,
        message="Promocode applied",
        code=promo.code,
        channel=promo.channel,
        percent_off=promo.percent_off,
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
    )
    result = validate_promo(db, payload, tenant_id=tenant_id)
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
    order.promo_free_delivery = free_del
    order.discount = discount
    if free_del:
        order.delivery_fee = Decimal("0")

    # Recalc total if possible
    try:
        sub = Decimal(str(order.subtotal or 0))
        fee = Decimal(str(order.delivery_fee or 0))
        order.total_amount = sub + fee - discount
        if order.total_amount < 0:
            order.total_amount = Decimal("0")
    except Exception:
        pass

    usage = PromoCodeUsage(
        promo_code_id=promo.id,
        order_id=order.id,
        user_id=order.customer_id,
        discount_amount=discount,
        percent_off_snapshot=promo.percent_off,
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
                free_delivery_applied=bool(u.free_delivery_applied),
                client_channel=u.client_channel,
                created_at=u.created_at,
                items=items,
            )
        )
    return rows
