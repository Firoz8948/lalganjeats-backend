from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.services import customers as customer_service
from app.modules.admin.schemas import CustomerStatusUpdate
from app.modules.users.models import User

router = APIRouter()


@router.get("/customers")
def get_all_customers(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return customer_service.get_all_customers(db, current.tenant_id)


@router.patch("/customers/{customer_id}/status")
def update_customer_status(
    customer_id: int,
    payload: CustomerStatusUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return customer_service.set_customer_status(
        db,
        current.tenant_id,
        customer_id,
        payload.is_active,
    )
