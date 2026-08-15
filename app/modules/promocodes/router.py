# backend/app/modules/promocodes/router.py
from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin, decode_token
from app.modules.users.models import User
from app.modules.promocodes import schemas, service

public_router = APIRouter(prefix="/api/v1/promocodes", tags=["Promocodes"])
admin_router = APIRouter(prefix="/api/v1/admin/promocodes", tags=["Admin Promocodes"])

_optional_bearer = HTTPBearer(auto_error=False)


def _optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return (
            db.query(User)
            .filter(User.id == int(user_id), User.is_active == True)
            .first()
        )
    except Exception:
        return None


@public_router.post("/validate", response_model=schemas.PromoValidateResponse)
def validate_promocode(
    payload: schemas.PromoValidateRequest,
    db: Session = Depends(get_db),
    current: User | None = Depends(_optional_user),
):
    """
    Validate a promocode for the given client_channel.
    Web → client_channel=web; Capacitor app → android_app | ios_app.
    mobile_app-only + web → download_required popup payload.
    """
    tenant_id = getattr(current, "tenant_id", None) if current else None
    return service.validate_promo(db, payload, tenant_id=tenant_id)


@admin_router.get("", response_model=list[schemas.PromoOut])
def list_promos(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.list_promos(db, current.tenant_id)


@admin_router.post("", response_model=schemas.PromoOut, status_code=201)
def create_promo(
    payload: schemas.PromoCreateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.create_promo(db, current.tenant_id, payload)


@admin_router.patch("/{promo_id}", response_model=schemas.PromoOut)
def update_promo(
    promo_id: int,
    payload: schemas.PromoUpdateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.update_promo(db, current.tenant_id, promo_id, payload)


@admin_router.delete("/{promo_id}")
def delete_promo(
    promo_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.delete_promo(db, current.tenant_id, promo_id)


@admin_router.get("/{promo_id}/usages", response_model=list[schemas.PromoUsageOut])
def promo_usages(
    promo_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.get_usages(db, current.tenant_id, promo_id)
