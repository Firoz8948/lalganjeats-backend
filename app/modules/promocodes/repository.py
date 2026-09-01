# backend/app/modules/promocodes/repository.py
from sqlalchemy.orm import Session, joinedload
from app.modules.promocodes.models import PromoCode, PromoCodeUsage
from app.modules.orders.models import Order


def get_by_id(db: Session, promo_id: int, tenant_id: int | None) -> PromoCode | None:
    q = db.query(PromoCode).filter(PromoCode.id == promo_id)
    if tenant_id is not None:
        q = q.filter(PromoCode.tenant_id == tenant_id)
    return q.first()


def get_by_code(
    db: Session, code: str, tenant_id: int | None = None
) -> PromoCode | None:
    q = db.query(PromoCode).filter(PromoCode.code == code.upper())
    if tenant_id is not None:
        q = q.filter(PromoCode.tenant_id == tenant_id)
    return q.first()


def list_promos(db: Session, tenant_id: int | None) -> list[PromoCode]:
    q = db.query(PromoCode)
    if tenant_id is not None:
        q = q.filter(PromoCode.tenant_id == tenant_id)
    return q.order_by(PromoCode.created_at.desc()).all()


def list_public_active(db: Session, tenant_id: int | None = None) -> list[PromoCode]:
    q = db.query(PromoCode).filter(
        PromoCode.is_active == True,
        PromoCode.is_public == True,
    )
    if tenant_id is not None:
        q = q.filter(
            (PromoCode.tenant_id == tenant_id) | (PromoCode.tenant_id.is_(None))
        )
    return q.order_by(PromoCode.created_at.desc()).all()


def list_usages(db: Session, promo_id: int) -> list[PromoCodeUsage]:
    return (
        db.query(PromoCodeUsage)
        .options(
            joinedload(PromoCodeUsage.user),
            joinedload(PromoCodeUsage.order).joinedload(Order.items),
            joinedload(PromoCodeUsage.order).joinedload(Order.restaurant),
        )
        .filter(PromoCodeUsage.promo_code_id == promo_id)
        .order_by(PromoCodeUsage.created_at.desc())
        .all()
    )


def list_usages_for_phone(
    db: Session, promo_id: int, phone_digits: str, user_id: int | None = None
) -> PromoCodeUsage | None:
    """Find an existing usage of this promo by this mobile / account."""
    if not phone_digits and not user_id:
        return None
    q = db.query(PromoCodeUsage).filter(PromoCodeUsage.promo_code_id == promo_id)
    if phone_digits and user_id:
        from sqlalchemy import or_

        return q.filter(
            or_(
                PromoCodeUsage.customer_phone == phone_digits,
                PromoCodeUsage.user_id == user_id,
            )
        ).first()
    if phone_digits:
        return q.filter(PromoCodeUsage.customer_phone == phone_digits).first()
    return q.filter(PromoCodeUsage.user_id == user_id).first()


def create(db: Session, promo: PromoCode) -> PromoCode:
    db.add(promo)
    db.flush()
    return promo
