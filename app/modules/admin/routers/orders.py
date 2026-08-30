from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.services import orders as order_service
from app.modules.users.models import User

router = APIRouter()


@router.get("/orders")
def get_all_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return order_service.get_all_orders(db, current, status=status)


@router.get("/orders/completed")
def get_completed_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    """Paginated completed (delivered) orders with customer info."""
    return order_service.get_completed_orders_paginated(
        db, current, page=page, page_size=page_size
    )


@router.get("/orders/{order_id}/breakdown")
def get_order_breakdown(
    order_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    """
    Money split for an order:
    - customer view: display + platform + delivery − discount
    - admin view: customer total − hotel − delivery
    """
    return order_service.get_order_breakdown(db, current, order_id)


@router.get("/payments/received")
def get_payments_received(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    """Orders where payment was successfully received (prepaid / collected)."""
    return order_service.get_payments_received(db, current)


@router.get("/delivery-earnings")
def get_delivery_earnings(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    """Delivery partner earnings, optionally filtered by date range."""
    return order_service.get_delivery_partner_earnings(
        db, current, start_date=start_date, end_date=end_date
    )

