from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.modules.users.models import User

PAGE_SIZE = 10


def _customer_query(db: Session, tenant_id: int):
    query = db.query(User).filter(User.role == "customer")
    if tenant_id is not None:
        query = query.filter(
            or_(User.tenant_id == tenant_id, User.tenant_id.is_(None))
        )
    return query


def count_tenant_customers(db: Session, tenant_id: int) -> int:
    """Registered customer accounts on this city, including those with no orders."""
    return int(_customer_query(db, tenant_id).count() or 0)


def get_all_customers(
    db: Session,
    tenant_id: int,
    page: int = 1,
    q: str | None = None,
):
    query = _customer_query(db, tenant_id)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        name_or_phone = [User.full_name.ilike(like), User.phone.ilike(like)]
        digits = "".join(ch for ch in term if ch.isdigit())
        if digits and digits != term:
            name_or_phone.append(User.phone.ilike(f"%{digits}%"))
        query = query.filter(or_(*name_or_phone))

    page = max(1, int(page or 1))
    total = int(
        query.with_entities(User.id).distinct().order_by(None).count() or 0
    )
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE if total else 0
    if page > total_pages > 0:
        page = total_pages

    customers = (
        query.distinct()
        .order_by(User.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    return {
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": total_pages,
        "items": [
            {
                "id": customer.id,
                "full_name": customer.full_name,
                "phone": customer.phone,
                "email": customer.email,
                "is_active": customer.is_active,
                "created_at": (
                    customer.created_at.isoformat()
                    if customer.created_at
                    else None
                ),
            }
            for customer in customers
        ],
    }


def set_customer_status(
    db: Session,
    tenant_id: int,
    customer_id: int,
    is_active: bool,
):
    customer = (
        _customer_query(db, tenant_id)
        .filter(User.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(404, "Customer not found for this tenant")
    customer.is_active = is_active
    db.commit()
    return {"id": customer.id, "is_active": bool(customer.is_active)}
