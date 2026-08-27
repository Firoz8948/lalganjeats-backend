from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
