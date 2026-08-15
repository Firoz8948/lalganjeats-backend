from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.services import dashboard as dashboard_service
from app.modules.users.models import User

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return dashboard_service.get_dashboard(db, current)
