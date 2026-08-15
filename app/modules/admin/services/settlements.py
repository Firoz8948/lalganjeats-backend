from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.modules.orders.models import Order
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User


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
        query = (
            query.join(Order, Order.id == DeliveryEarning.order_id)
            .filter(Order.tenant_id == current.tenant_id)
        )

    rows = (
        query.group_by(User.id, User.full_name, User.phone)
        .order_by(User.full_name)
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.full_name or row.phone or f"Partner #{row.id}",
            "phone": row.phone,
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
