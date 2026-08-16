import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.modules.admin.models import ImpersonationSession
from app.modules.admin.services.restaurants import IMPERSONATION_TTL_MINUTES
from app.modules.orders.models import Order
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User


DELIVERY_IMPERSONATION_PURPOSE = "delivery_admin_impersonation"


def validate_delivery_impersonation_target(admin: User, partner: User) -> User:
    """Return a delivery partner only when owned by the admin's tenant."""
    if admin.role != "admin" or admin.tenant_id is None:
        raise HTTPException(403, "Tenant admin access required")
    if partner.tenant_id != admin.tenant_id or partner.role != "delivery_partner":
        raise HTTPException(404, "Delivery partner not found")
    if not partner.is_active:
        raise HTTPException(400, "Delivery partner is inactive")
    return partner


def impersonate_delivery_partner(
    db: Session,
    partner_id: int,
    admin: User,
    request: Request | None = None,
) -> dict:
    partner = db.query(User).filter(User.id == partner_id).first()
    if not partner:
        raise HTTPException(404, "Delivery partner not found")
    partner = validate_delivery_impersonation_target(admin, partner)

    jti = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=IMPERSONATION_TTL_MINUTES
    )
    audit = ImpersonationSession(
        jti=jti,
        admin_user_id=admin.id,
        owner_user_id=partner.id,
        restaurant_id=None,
        tenant_id=admin.tenant_id,
        purpose=DELIVERY_IMPERSONATION_PURPOSE,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        expires_at=expires_at,
    )
    db.add(audit)
    db.commit()

    token = create_access_token(
        {
            "sub": str(partner.id),
            "role": "delivery_partner",
            "tenant_id": admin.tenant_id,
            "impersonated_by": admin.id,
            "impersonation_type": "delivery_partner",
            "impersonation_session_id": jti,
            "purpose": DELIVERY_IMPERSONATION_PURPOSE,
        },
        expires_delta=timedelta(minutes=IMPERSONATION_TTL_MINUTES),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "delivery_partner",
        "user_id": partner.id,
        "full_name": partner.full_name,
        "phone": partner.phone,
        "impersonated_by": admin.id,
        "impersonation_session_id": jti,
        "redirect_to": "/deliverypartner/home",
    }


def list_restaurant_settlements(db: Session, current: User):
    unsettled_amount = func.coalesce(func.sum(case(
        (
            RestaurantEarning.transfer_status == "unsettled",
            RestaurantEarning.amount_earned,
        ),
        else_=0,
    )), 0)
    unsettled_orders = func.count(case(
        (RestaurantEarning.transfer_status == "unsettled", 1),
    ))
    settled_amount = func.coalesce(func.sum(case(
        (
            RestaurantEarning.transfer_status.in_(["settled", "completed"]),
            RestaurantEarning.amount_earned,
        ),
        else_=0,
    )), 0)

    query = (
        db.query(
            Restaurant.id,
            Restaurant.name,
            unsettled_amount.label("unsettled_amount"),
            unsettled_orders.label("unsettled_orders"),
            settled_amount.label("settled_amount_lifetime"),
        )
        .outerjoin(
            RestaurantEarning,
            RestaurantEarning.restaurant_id == Restaurant.id,
        )
    )
    if current.tenant_id:
        query = query.filter(Restaurant.tenant_id == current.tenant_id)

    rows = (
        query.group_by(Restaurant.id, Restaurant.name)
        .order_by(Restaurant.name)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "unsettled_amount": round(
                float(row.unsettled_amount or 0),
                2,
            ),
            "unsettled_orders": int(row.unsettled_orders or 0),
            "settled_amount_lifetime": round(
                float(row.settled_amount_lifetime or 0),
                2,
            ),
        }
        for row in rows
    ]


def list_delivery_settlements(db: Session, current: User):
    unsettled_amount = func.coalesce(func.sum(case(
        (
            DeliveryEarning.transfer_status == "unsettled",
            DeliveryEarning.amount_earned,
        ),
        else_=0,
    )), 0)
    unsettled_orders = func.count(case(
        (DeliveryEarning.transfer_status == "unsettled", 1),
    ))
    settled_amount = func.coalesce(func.sum(case(
        (
            DeliveryEarning.transfer_status.in_(["settled", "completed"]),
            DeliveryEarning.amount_earned,
        ),
        else_=0,
    )), 0)

    query = (
        db.query(
            User.id,
            User.full_name,
            User.phone,
            User.is_active,
            unsettled_amount.label("unsettled_amount"),
            unsettled_orders.label("unsettled_orders"),
            settled_amount.label("settled_amount_lifetime"),
        )
        .outerjoin(
            DeliveryEarning,
            DeliveryEarning.delivery_partner_id == User.id,
        )
        .filter(User.role == "delivery_partner")
    )
    if current.tenant_id:
        query = query.filter(User.tenant_id == current.tenant_id)

    rows = (
        query.group_by(User.id, User.full_name, User.phone, User.is_active)
        .order_by(User.full_name)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.full_name or row.phone or f"Partner #{row.id}",
            "phone": row.phone,
            "is_active": bool(row.is_active),
            "unsettled_amount": round(
                float(row.unsettled_amount or 0),
                2,
            ),
            "unsettled_orders": int(row.unsettled_orders or 0),
            "settled_amount_lifetime": round(
                float(row.settled_amount_lifetime or 0),
                2,
            ),
        }
        for row in rows
    ]


def settle_restaurant_earnings(
    db: Session,
    current: User,
    restaurant_id: int,
):
    restaurant_query = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id
    )
    if current.tenant_id:
        restaurant_query = restaurant_query.filter(
            Restaurant.tenant_id == current.tenant_id
        )
    if not restaurant_query.first():
        raise HTTPException(404, "Restaurant not found")

    rows = db.query(RestaurantEarning).filter(
        RestaurantEarning.restaurant_id == restaurant_id,
        RestaurantEarning.transfer_status == "unsettled",
    ).all()
    if not rows:
        raise HTTPException(400, "No unsettled restaurant earnings")

    settled_at = datetime.now(timezone.utc)
    amount = round(sum(float(row.amount_earned) for row in rows), 2)
    for row in rows:
        row.transfer_status = "settled"
        row.settled_at = settled_at
        row.settled_by = current.id
    db.commit()
    return {"settled_amount": amount, "settled_orders": len(rows)}


def settle_delivery_earnings(
    db: Session,
    current: User,
    partner_id: int,
):
    query = db.query(DeliveryEarning).filter(
        DeliveryEarning.delivery_partner_id == partner_id,
        DeliveryEarning.transfer_status == "unsettled",
    )
    if current.tenant_id:
        query = query.join(
            Order,
            Order.id == DeliveryEarning.order_id,
        ).filter(Order.tenant_id == current.tenant_id)
    rows = query.all()
    if not rows:
        raise HTTPException(
            400,
            "No unsettled delivery-partner earnings",
        )

    settled_at = datetime.now(timezone.utc)
    amount = round(sum(float(row.amount_earned) for row in rows), 2)
    for row in rows:
        row.transfer_status = "settled"
        row.settled_at = settled_at
        row.settled_by = current.id
    db.commit()
    return {"settled_amount": amount, "settled_orders": len(rows)}
