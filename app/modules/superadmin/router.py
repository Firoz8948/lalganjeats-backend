# backend/app/modules/superadmin/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_super_admin
from app.modules.users.models import User
from app.modules.superadmin import schemas, service

router = APIRouter(prefix="/api/v1/superadmin", tags=["Super Admin"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    tenants = service.list_tenants(db)
    return {
        "stats": {
            "total_tenants": len(tenants),
            "active_tenants": sum(1 for t in tenants if t.is_active),
            "total_restaurants": sum(t.restaurant_count for t in tenants),
        },
        "tenants": tenants,
    }


@router.get("/tenants", response_model=list[schemas.TenantListItem])
def list_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.list_tenants(db)


@router.post("/tenants", response_model=schemas.TenantOut, status_code=201)
def create_tenant(
    payload: schemas.TenantCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.create_tenant(db, payload)


@router.get("/tenants/{tenant_id}", response_model=schemas.TenantOut)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.get_tenant(db, tenant_id)


@router.patch("/tenants/{tenant_id}", response_model=schemas.TenantOut)
def update_tenant(
    tenant_id: int,
    payload: schemas.TenantUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.update_tenant(db, tenant_id, payload)


@router.patch("/tenants/{tenant_id}/activate", response_model=schemas.TenantOut)
def activate_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.set_tenant_active(db, tenant_id, True)


@router.patch("/tenants/{tenant_id}/deactivate", response_model=schemas.TenantOut)
def deactivate_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.set_tenant_active(db, tenant_id, False)


@router.post("/tenants/{tenant_id}/reset-password")
def reset_admin_password(
    tenant_id: int,
    payload: schemas.TenantAdminResetPassword,
    db: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return service.reset_admin_password(db, tenant_id, payload.new_password)


@router.post(
    "/tenants/{tenant_id}/impersonate",
    response_model=schemas.ImpersonateResponse,
)
def impersonate_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_super_admin),
):
    """Issue an admin JWT for the tenant — UI switches into /admin as that admin."""
    return service.impersonate_tenant(db, tenant_id, current)
