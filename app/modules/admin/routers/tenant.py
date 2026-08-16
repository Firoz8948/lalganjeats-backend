from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.superadmin import schemas as tenant_schemas
from app.modules.superadmin import service as tenant_service
from app.modules.users.models import User

router = APIRouter()


@router.get("/tenant", response_model=tenant_schemas.TenantCentreOut)
def get_my_tenant(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    """Centre address/lat/long are read-only for admin."""
    return tenant_service.get_admin_centre(db, current)


@router.get("/zones", response_model=list[tenant_schemas.ZoneOut])
def list_zones(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    centre = tenant_service.get_admin_centre(db, current)
    return centre.zones


@router.post(
    "/zones",
    response_model=tenant_schemas.ZoneOut,
    status_code=201,
)
def create_zone(
    payload: tenant_schemas.ZoneCreateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return tenant_service.create_zone(db, current, payload)


@router.patch(
    "/zones/{zone_id}",
    response_model=tenant_schemas.ZoneOut,
)
def update_zone(
    zone_id: int,
    payload: tenant_schemas.ZoneUpdateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return tenant_service.update_zone(db, current, zone_id, payload)


@router.delete("/zones/{zone_id}")
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return tenant_service.delete_zone(db, current, zone_id)


@router.post(
    "/delivery-exceptions",
    response_model=tenant_schemas.DeliveryExceptionOut,
    status_code=201,
)
def create_delivery_exception(
    payload: tenant_schemas.DeliveryExceptionCreateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return tenant_service.create_delivery_exception(db, current, payload)


@router.patch(
    "/delivery-exceptions/{exception_id}",
    response_model=tenant_schemas.DeliveryExceptionOut,
)
def update_delivery_exception(
    exception_id: int,
    payload: tenant_schemas.DeliveryExceptionUpdateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return tenant_service.update_delivery_exception(
        db,
        current,
        exception_id,
        payload,
    )


@router.delete("/delivery-exceptions/{exception_id}")
def delete_delivery_exception(
    exception_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return tenant_service.delete_delivery_exception(
        db,
        current,
        exception_id,
    )
