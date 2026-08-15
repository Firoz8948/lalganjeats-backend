# backend/app/modules/superadmin/repository.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.modules.superadmin.models import Tenant, DeliveryZone
from app.modules.restaurants.models import Restaurant


def get_tenant_by_id(db: Session, tenant_id: int) -> Tenant | None:
    return (
        db.query(Tenant)
        .options(joinedload(Tenant.admin_user), joinedload(Tenant.zones))
        .filter(Tenant.id == tenant_id)
        .first()
    )


def get_tenant_by_slug(db: Session, slug: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.slug == slug).first()


def get_tenant_by_admin_user(db: Session, user_id: int) -> Tenant | None:
    return (
        db.query(Tenant)
        .options(joinedload(Tenant.zones))
        .filter(Tenant.admin_user_id == user_id)
        .first()
    )


def list_tenants(db: Session) -> list[Tenant]:
    return (
        db.query(Tenant)
        .options(joinedload(Tenant.admin_user), joinedload(Tenant.zones))
        .order_by(Tenant.created_at.desc())
        .all()
    )


def count_restaurants(db: Session, tenant_id: int) -> int:
    return (
        db.query(func.count(Restaurant.id))
        .filter(Restaurant.tenant_id == tenant_id)
        .scalar()
        or 0
    )


def create_tenant(db: Session, tenant: Tenant) -> Tenant:
    db.add(tenant)
    db.flush()
    return tenant


def get_zone(db: Session, zone_id: int, tenant_id: int) -> DeliveryZone | None:
    return (
        db.query(DeliveryZone)
        .filter(DeliveryZone.id == zone_id, DeliveryZone.tenant_id == tenant_id)
        .first()
    )


def list_zones(db: Session, tenant_id: int) -> list[DeliveryZone]:
    return (
        db.query(DeliveryZone)
        .filter(DeliveryZone.tenant_id == tenant_id)
        .order_by(DeliveryZone.sort_order, DeliveryZone.radius_km)
        .all()
    )


def create_zone(db: Session, zone: DeliveryZone) -> DeliveryZone:
    db.add(zone)
    db.flush()
    return zone


def delete_zone(db: Session, zone: DeliveryZone) -> None:
    db.delete(zone)
