from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import case, func, literal
from sqlalchemy.orm import Session, joinedload

from app.modules.admin.reports.schemas import ReportRequest
from app.modules.orders.models import Order
from app.modules.payments.models import DeliveryEarning, RestaurantEarning
from app.modules.restaurants.models import Restaurant
from app.modules.users.models import User


PUBLIC_REPORT_KEYS = {
    "target_type",
    "target_id",
    "target_name",
    "period",
    "period_label",
    "period_start",
    "period_end",
    "generated_at",
    "order_count",
    "delivered_orders",
    "cancelled_orders",
    "gross_order_value",
    "discounts",
    "delivery_fees",
    "platform_charges",
    "gross_earnings",
    "platform_fees",
    "settled_amount",
    "unsettled_amount",
    "settled_orders",
    "unsettled_orders",
}

PERIOD_LABELS = {
    "daily": "Today",
    "last_week": "Last 7 days",
    "last_month": "Last 30 days",
    "overall": "Overall",
    "custom": "Custom range",
}
IST = timezone(timedelta(hours=5, minutes=30))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def resolve_period(
    period: str,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    end = _aware(now or datetime.now(timezone.utc))
    if period == "daily":
        local_start = end.astimezone(IST).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return local_start.astimezone(timezone.utc), end
    if period == "last_week":
        return end - timedelta(days=7), end
    if period == "last_month":
        return end - timedelta(days=30), end
    if period == "overall":
        return datetime(1970, 1, 1, tzinfo=timezone.utc), end
    if period == "custom":
        if custom_start is None or custom_end is None:
            raise HTTPException(400, "Custom start and end dates are required")
        start, custom_end = _aware(custom_start), _aware(custom_end)
        if start >= custom_end:
            raise HTTPException(400, "Custom end must be after custom start")
        if custom_end > end + timedelta(minutes=5):
            raise HTTPException(400, "Custom end cannot be in the future")
        return start, custom_end
    raise HTTPException(400, "Invalid report period")


def validate_report_target(admin, target, target_type: str):
    if admin.role != "admin" or admin.tenant_id is None:
        raise HTTPException(403, "Tenant admin access required")
    if target is None or target.tenant_id != admin.tenant_id:
        raise HTTPException(404, "Report recipient not found")
    if target_type == "delivery_partner" and target.role != "delivery_partner":
        raise HTTPException(404, "Report recipient not found")
    if not target.is_active:
        raise HTTPException(400, "Report recipient is inactive")
    return target


def list_recipients(db: Session, admin: User) -> list[dict]:
    restaurants = (
        db.query(Restaurant)
        .options(joinedload(Restaurant.owner))
        .filter(Restaurant.tenant_id == admin.tenant_id)
        .order_by(Restaurant.name)
        .all()
    )
    partners = (
        db.query(User)
        .filter(
            User.tenant_id == admin.tenant_id,
            User.role == "delivery_partner",
        )
        .order_by(User.full_name)
        .all()
    )
    result = [
        {
            "id": row.id,
            "target_type": "restaurant",
            "name": row.name,
            "phone": row.owner.phone if row.owner else row.phone,
            "email": row.owner.email if row.owner else None,
            "is_active": bool(row.is_active and row.owner and row.owner.is_active),
        }
        for row in restaurants
    ]
    result.extend(
        {
            "id": row.id,
            "target_type": "delivery_partner",
            "name": row.full_name or row.phone or f"Partner #{row.id}",
            "phone": row.phone,
            "email": row.email,
            "is_active": bool(row.is_active),
        }
        for row in partners
    )
    return result


def _load_target(db: Session, admin: User, target_type: str, target_id: int):
    if target_type == "restaurant":
        target = (
            db.query(Restaurant)
            .options(joinedload(Restaurant.owner))
            .filter(Restaurant.id == target_id)
            .first()
        )
        validate_report_target(admin, target, target_type)
        return target, target.name
    target = db.query(User).filter(User.id == target_id).first()
    validate_report_target(admin, target, target_type)
    return target, target.full_name or target.phone or f"Partner #{target.id}"


def get_target_contact(
    db: Session,
    admin: User,
    target_type: str,
    target_id: int,
) -> tuple[str | None, str | None]:
    target, _ = _load_target(db, admin, target_type, target_id)
    if target_type == "restaurant":
        return (
            target.owner.email if target.owner else None,
            target.owner.phone if target.owner else target.phone,
        )
    return target.email, target.phone


def build_report(db: Session, admin: User, request: ReportRequest) -> dict:
    target, target_name = _load_target(
        db,
        admin,
        request.target_type,
        request.target_id,
    )
    start, end = resolve_period(
        request.period,
        request.custom_start,
        request.custom_end,
    )
    target_filter = (
        Order.restaurant_id == target.id
        if request.target_type == "restaurant"
        else Order.delivery_partner_id == target.id
    )
    order_row = (
        db.query(
            func.count(Order.id).label("order_count"),
            func.count(case((Order.status == "delivered", 1))).label(
                "delivered_orders"
            ),
            func.count(case((Order.status == "cancelled", 1))).label(
                "cancelled_orders"
            ),
            func.coalesce(func.sum(Order.total_amount), 0).label("gross_order_value"),
            func.coalesce(func.sum(Order.discount), 0).label("discounts"),
            func.coalesce(func.sum(Order.delivery_fee), 0).label("delivery_fees"),
            func.coalesce(func.sum(Order.platform_fee), 0).label("platform_charges"),
        )
        .filter(
            target_filter,
            Order.tenant_id == admin.tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .one()
    )

    earning_model = (
        RestaurantEarning
        if request.target_type == "restaurant"
        else DeliveryEarning
    )
    earning_target = (
        RestaurantEarning.restaurant_id == target.id
        if request.target_type == "restaurant"
        else DeliveryEarning.delivery_partner_id == target.id
    )
    platform_fee = (
        func.coalesce(func.sum(RestaurantEarning.platform_fee), 0)
        if request.target_type == "restaurant"
        else literal(0.0)
    )
    earning_row = (
        db.query(
            func.coalesce(func.sum(earning_model.amount_earned), 0).label(
                "gross_earnings"
            ),
            platform_fee.label("platform_fees"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            earning_model.transfer_status.in_(["settled", "completed"]),
                            earning_model.amount_earned,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("settled_amount"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            earning_model.transfer_status == "unsettled",
                            earning_model.amount_earned,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("unsettled_amount"),
            func.count(
                case(
                    (
                        earning_model.transfer_status.in_(["settled", "completed"]),
                        1,
                    )
                )
            ).label("settled_orders"),
            func.count(
                case((earning_model.transfer_status == "unsettled", 1))
            ).label("unsettled_orders"),
        )
        .join(Order, Order.id == earning_model.order_id)
        .filter(
            earning_target,
            Order.tenant_id == admin.tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .one()
    )
    now = datetime.now(timezone.utc)
    return {
        "target_type": request.target_type,
        "target_id": target.id,
        "target_name": target_name,
        "period": request.period,
        "period_label": PERIOD_LABELS[request.period],
        "period_start": start,
        "period_end": end,
        "generated_at": now,
        "order_count": int(order_row.order_count or 0),
        "delivered_orders": int(order_row.delivered_orders or 0),
        "cancelled_orders": int(order_row.cancelled_orders or 0),
        "gross_order_value": round(float(order_row.gross_order_value or 0), 2),
        "discounts": round(float(order_row.discounts or 0), 2),
        "delivery_fees": round(float(order_row.delivery_fees or 0), 2),
        "platform_charges": round(float(order_row.platform_charges or 0), 2),
        "gross_earnings": round(float(earning_row.gross_earnings or 0), 2),
        "platform_fees": round(float(earning_row.platform_fees or 0), 2),
        "settled_amount": round(float(earning_row.settled_amount or 0), 2),
        "unsettled_amount": round(float(earning_row.unsettled_amount or 0), 2),
        "settled_orders": int(earning_row.settled_orders or 0),
        "unsettled_orders": int(earning_row.unsettled_orders or 0),
    }
