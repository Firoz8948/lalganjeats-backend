# backend/app/modules/superadmin/service.py
import re
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.security import hash_password, create_access_token
from app.modules.users.models import User
from app.modules.superadmin.models import Tenant, DeliveryZone
from app.modules.superadmin import repository as repo
from app.modules.superadmin.schemas import (
    TenantCreateRequest,
    TenantUpdateRequest,
    ZoneCreateRequest,
    ZoneUpdateRequest,
    TenantOut,
    TenantListItem,
    ZoneOut,
    TenantCentreOut,
    ImpersonateResponse,
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    n = 1
    while repo.get_tenant_by_slug(db, slug):
        n += 1
        slug = f"{base}-{n}"
    return slug


def _tenant_out(db: Session, tenant: Tenant) -> TenantOut:
    admin = tenant.admin_user
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        admin_user_id=tenant.admin_user_id,
        admin_email=admin.email if admin else None,
        admin_full_name=admin.full_name if admin else None,
        center_latitude=tenant.center_latitude,
        center_longitude=tenant.center_longitude,
        center_address=tenant.center_address,
        one_time_fee=tenant.one_time_fee,
        platform_charge_percent=tenant.platform_charge_percent,
        bank_account_holder_name=tenant.bank_account_holder_name,
        bank_account_number=tenant.bank_account_number,
        bank_ifsc_code=tenant.bank_ifsc_code,
        bank_name=tenant.bank_name,
        is_active=tenant.is_active,
        zones=[ZoneOut.model_validate(z) for z in (tenant.zones or [])],
        restaurant_count=repo.count_restaurants(db, tenant.id),
    )


def list_tenants(db: Session) -> list[TenantListItem]:
    items = []
    for t in repo.list_tenants(db):
        admin = t.admin_user
        items.append(
            TenantListItem(
                id=t.id,
                name=t.name,
                slug=t.slug,
                admin_email=admin.email if admin else None,
                center_address=t.center_address,
                center_latitude=t.center_latitude,
                center_longitude=t.center_longitude,
                one_time_fee=t.one_time_fee,
                platform_charge_percent=t.platform_charge_percent,
                bank_account_number=t.bank_account_number,
                is_active=t.is_active,
                restaurant_count=repo.count_restaurants(db, t.id),
                zone_count=len(t.zones or []),
            )
        )
    return items


def get_tenant(db: Session, tenant_id: int) -> TenantOut:
    tenant = repo.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_out(db, tenant)


def create_tenant(db: Session, payload: TenantCreateRequest) -> TenantOut:
    existing_user = db.query(User).filter(User.email == payload.admin_email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this admin email already exists",
        )

    base_slug = payload.slug or _slugify(payload.name)
    slug = _unique_slug(db, base_slug)

    admin = User(
        full_name=payload.admin_full_name,
        email=payload.admin_email,
        password_hash=hash_password(payload.admin_password),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    db.flush()

    tenant = Tenant(
        name=payload.name.strip(),
        slug=slug,
        admin_user_id=admin.id,
        center_latitude=payload.center_latitude,
        center_longitude=payload.center_longitude,
        center_address=payload.center_address.strip(),
        one_time_fee=payload.one_time_fee,
        platform_charge_percent=payload.platform_charge_percent,
        bank_account_holder_name=(payload.bank_account_holder_name or None),
        bank_account_number=(payload.bank_account_number or None),
        bank_ifsc_code=(payload.bank_ifsc_code or None),
        bank_name=(payload.bank_name or None),
        is_active=True,
    )
    repo.create_tenant(db, tenant)
    admin.tenant_id = tenant.id
    db.commit()

    tenant = repo.get_tenant_by_id(db, tenant.id)
    return _tenant_out(db, tenant)


def update_tenant(
    db: Session, tenant_id: int, payload: TenantUpdateRequest
) -> TenantOut:
    tenant = repo.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    data = payload.model_dump(exclude_unset=True)

    # Admin profile fields (not columns on Tenant)
    admin_email = data.pop("admin_email", None)
    admin_full_name = data.pop("admin_full_name", None)
    admin_password = data.pop("admin_password", None)

    for key, value in data.items():
        setattr(tenant, key, value)

    admin = tenant.admin_user
    if admin:
        if admin_full_name is not None:
            admin.full_name = admin_full_name
        if admin_email is not None and admin_email != admin.email:
            clash = (
                db.query(User)
                .filter(User.email == admin_email, User.id != admin.id)
                .first()
            )
            if clash:
                raise HTTPException(400, detail="Admin email already in use")
            admin.email = admin_email
        if admin_password:
            admin.password_hash = hash_password(admin_password)

    db.commit()
    tenant = repo.get_tenant_by_id(db, tenant_id)
    return _tenant_out(db, tenant)


def set_tenant_active(db: Session, tenant_id: int, is_active: bool) -> TenantOut:
    tenant = repo.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.is_active = is_active
    if tenant.admin_user:
        tenant.admin_user.is_active = is_active
    db.commit()
    return _tenant_out(db, repo.get_tenant_by_id(db, tenant_id))


def reset_admin_password(db: Session, tenant_id: int, new_password: str) -> dict:
    tenant = repo.get_tenant_by_id(db, tenant_id)
    if not tenant or not tenant.admin_user:
        raise HTTPException(status_code=404, detail="Tenant admin not found")
    tenant.admin_user.password_hash = hash_password(new_password)
    db.commit()
    return {"message": "Admin password updated"}


def impersonate_tenant(
    db: Session, tenant_id: int, super_admin: User
) -> ImpersonateResponse:
    tenant = repo.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.is_active:
        raise HTTPException(status_code=400, detail="Tenant is inactive")
    admin = tenant.admin_user
    if not admin or not admin.is_active:
        raise HTTPException(status_code=400, detail="Tenant admin is inactive")

    token = create_access_token(
        {
            "sub": str(admin.id),
            "role": "admin",
            "tenant_id": tenant.id,
            "impersonated_by": super_admin.id,
        }
    )
    return ImpersonateResponse(
        access_token=token,
        role="admin",
        user_id=admin.id,
        full_name=admin.full_name,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        impersonated_by=super_admin.id,
    )


# ── Zones (tenant admin) ─────────────────────────────────────────────────────

def require_admin_tenant(db: Session, admin: User) -> Tenant:
    if not admin.tenant_id:
        # Fallback: look up by admin_user_id
        tenant = repo.get_tenant_by_admin_user(db, admin.id)
        if not tenant:
            raise HTTPException(
                status_code=400,
                detail="Admin is not linked to a tenant",
            )
        return tenant
    tenant = repo.get_tenant_by_id(db, admin.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def get_admin_centre(db: Session, admin: User) -> TenantCentreOut:
    tenant = require_admin_tenant(db, admin)
    return TenantCentreOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        center_latitude=tenant.center_latitude,
        center_longitude=tenant.center_longitude,
        center_address=tenant.center_address,
        platform_charge_percent=tenant.platform_charge_percent,
        zones=[ZoneOut.model_validate(z) for z in repo.list_zones(db, tenant.id)],
    )


def create_zone(
    db: Session, admin: User, payload: ZoneCreateRequest
) -> ZoneOut:
    tenant = require_admin_tenant(db, admin)
    zone = DeliveryZone(
        tenant_id=tenant.id,
        name=payload.name.strip(),
        radius_km=payload.radius_km,
        pricing_type=payload.pricing_type,
        rate=payload.rate,
        sort_order=payload.sort_order,
        is_active=True,
    )
    try:
        repo.create_zone(db, zone)
        db.commit()
        db.refresh(zone)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Could not create zone (duplicate name?)",
        )
    return ZoneOut.model_validate(zone)


def update_zone(
    db: Session, admin: User, zone_id: int, payload: ZoneUpdateRequest
) -> ZoneOut:
    tenant = require_admin_tenant(db, admin)
    zone = repo.get_zone(db, zone_id, tenant.id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, key, value)
    db.commit()
    db.refresh(zone)
    return ZoneOut.model_validate(zone)


def delete_zone(db: Session, admin: User, zone_id: int) -> dict:
    tenant = require_admin_tenant(db, admin)
    zone = repo.get_zone(db, zone_id, tenant.id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    repo.delete_zone(db, zone)
    db.commit()
    return {"message": "Zone deleted"}
