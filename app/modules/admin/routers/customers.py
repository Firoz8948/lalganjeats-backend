from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.services import customers as customer_service

router = APIRouter()


@router.get("/customers")
def get_all_customers(
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return customer_service.get_all_customers(db)
