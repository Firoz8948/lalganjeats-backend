from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.schemas import DeliveryPartnerImpersonationResponse
from app.modules.admin.services import settlements as settlement_service
from app.modules.users.models import User

router = APIRouter()


@router.get("/settlements/restaurants")
def list_restaurant_settlements(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.list_restaurant_settlements(db, current)


@router.get("/settlements/delivery-partners")
def list_delivery_settlements(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.list_delivery_settlements(db, current)


@router.post(
    "/delivery-partners/{partner_id}/impersonate",
    response_model=DeliveryPartnerImpersonationResponse,
)
def impersonate_delivery_partner(
    partner_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.impersonate_delivery_partner(
        db,
        partner_id,
        current,
        request=request,
    )


@router.post("/settlements/restaurants/{restaurant_id}/settle")
def settle_restaurant_earnings(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.settle_restaurant_earnings(
        db,
        current,
        restaurant_id,
    )


@router.post("/settlements/delivery-partners/{partner_id}/settle")
def settle_delivery_earnings(
    partner_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.settle_delivery_earnings(
        db,
        current,
        partner_id,
    )
