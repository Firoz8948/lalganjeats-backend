"""Paginated settlement and cash-clear history (page size 10)."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.payments.cash_remittance import parse_order_ids
from app.modules.payments.models import CashRemittance, DeliveryEarning, RestaurantEarning

PAGE_SIZE = 10


def paginated_result(*, page: int, page_size: int, total: int, items: list) -> dict:
    page = max(1, int(page or 1))
    size = PAGE_SIZE
    total = int(total or 0)
    total_pages = (total + size - 1) // size if total else 0
    if page > total_pages > 0:
        page = total_pages
    return {
        "page": page,
        "page_size": size,
        "total": total,
        "total_pages": total_pages,
        "items": items,
    }


def cash_status_label(status: str | None) -> str:
    key = (status or "").strip().lower()
    if key == "paid":
        return "Paid"
    if key in ("failed", "cancelled"):
        return "Payment cancelled"
    return "Pending"


def _offset(page: int) -> int:
    return (max(1, page) - 1) * PAGE_SIZE


def settlement_history(
    db: Session,
    *,
    model,
    owner_column,
    owner_id: int,
    page: int = 1,
) -> dict:
    page = max(1, int(page or 1))
    grouped = (
        db.query(
            model.settled_at.label("settled_at"),
            func.count(model.id).label("order_count"),
            func.coalesce(func.sum(model.amount_earned), 0).label("amount"),
        )
        .filter(
            owner_column == owner_id,
            model.transfer_status.in_(["settled", "completed"]),
            model.settled_at.isnot(None),
        )
        .group_by(model.settled_at)
        .order_by(model.settled_at.desc())
    )
    sub = grouped.subquery()
    total = int(db.query(func.count()).select_from(sub).scalar() or 0)
    page = min(page, max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)) if total else 1
    rows = (
        db.query(sub)
        .order_by(sub.c.settled_at.desc())
        .offset(_offset(page))
        .limit(PAGE_SIZE)
        .all()
    )
    items = [
        {
            "settled_at": row.settled_at.isoformat() if row.settled_at else None,
            "order_count": int(row.order_count or 0),
            "amount": round(float(row.amount or 0), 2),
        }
        for row in rows
    ]
    return paginated_result(page=page, page_size=PAGE_SIZE, total=total, items=items)


def restaurant_settlement_history(db: Session, restaurant_id: int, page: int = 1) -> dict:
    return settlement_history(
        db,
        model=RestaurantEarning,
        owner_column=RestaurantEarning.restaurant_id,
        owner_id=restaurant_id,
        page=page,
    )


def delivery_settlement_history(db: Session, partner_id: int, page: int = 1) -> dict:
    return settlement_history(
        db,
        model=DeliveryEarning,
        owner_column=DeliveryEarning.delivery_partner_id,
        owner_id=partner_id,
        page=page,
    )


def cash_remittance_history(db: Session, partner_id: int, page: int = 1) -> dict:
    page = max(1, int(page or 1))
    query = (
        db.query(CashRemittance)
        .filter(CashRemittance.delivery_partner_id == partner_id)
        .order_by(CashRemittance.created_at.desc())
    )
    total = int(query.count() or 0)
    page = min(page, max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)) if total else 1
    rows = query.offset(_offset(page)).limit(PAGE_SIZE).all()
    items = [
        {
            "id": row.id,
            "amount": round(float(row.amount or 0), 2),
            "order_count": len(parse_order_ids(row.order_ids)),
            "status": row.status,
            "status_label": cash_status_label(row.status),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        }
        for row in rows
    ]
    return paginated_result(page=page, page_size=PAGE_SIZE, total=total, items=items)
