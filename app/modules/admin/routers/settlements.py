from fastapi import APIRouter, Depends, Query, Request
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


@router.get("/settlements/restaurants/{restaurant_id}/history")
def restaurant_settlement_history(
    restaurant_id: int,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.restaurant_settlement_history(
        db, current, restaurant_id, page
    )


@router.get("/settlements/delivery-partners/{partner_id}/history")
def delivery_settlement_history(
    partner_id: int,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.delivery_settlement_history(
        db, current, partner_id, page
    )


@router.get("/settlements/delivery-partners/{partner_id}/cash-history")
def delivery_cash_history(
    partner_id: int,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return settlement_service.delivery_cash_history(db, current, partner_id, page)
