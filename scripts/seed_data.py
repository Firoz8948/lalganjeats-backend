"""
Seed platform super admin + migrate legacy admin → tenant admin.
Run: python -m scripts.seed_data
"""
from decimal import Decimal
from app.core.database import SessionLocal, engine, Base
from app.core.security import hash_password

# Register models before create_all / queries
from app.modules.superadmin.models import Tenant, DeliveryZone  # noqa: F401
from app.modules.users.models import User
from app.modules.restaurants.models import Restaurant  # noqa: F401
from app.modules.auth.models import OTP  # noqa: F401
from app.modules.orders.models import Order, OrderItem, DeliveryProfile  # noqa: F401
from app.modules.payments.models import (  # noqa: F401
    PaymentSettings, RestaurantEarning, DeliveryEarning, Withdrawal, BankAccount,
)
from app.modules.banners.models import HomeBannerSlide  # noqa: F401

Base.metadata.create_all(bind=engine)

# Platform owner
SUPERADMIN_EMAIL = "superadmin"
SUPERADMIN_PASSWORD = "superadmin"

# Existing tenant admin (was previously role=super_admin)
ADMIN_EMAIL = "admin"
ADMIN_PASSWORD = "admin"
LEGACY_ADMIN_EMAIL = "admin@lalganjeats.com"

# Default centre for the first tenant (Lalganj, UP approx)
DEFAULT_LAT = Decimal("26.1635000")
DEFAULT_LNG = Decimal("80.9345000")
DEFAULT_ADDRESS = "Lalganj, Uttar Pradesh, India"


def _ensure_superadmin(db):
    user = db.query(User).filter(
        User.email == SUPERADMIN_EMAIL,
        User.role == "super_admin",
    ).first()
    if user:
        user.password_hash = hash_password(SUPERADMIN_PASSWORD)
        user.full_name = user.full_name or "Platform Super Admin"
        user.is_active = True
        user.is_verified = True
        db.commit()
        print(f"Updated super admin: {SUPERADMIN_EMAIL} / {SUPERADMIN_PASSWORD}")
        return user

    user = User(
        full_name="Platform Super Admin",
        email=SUPERADMIN_EMAIL,
        password_hash=hash_password(SUPERADMIN_PASSWORD),
        role="super_admin",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    print(f"Created super admin: {SUPERADMIN_EMAIL} / {SUPERADMIN_PASSWORD}")
    return user


def _migrate_legacy_super_admins(db):
    """Any leftover role=super_admin that is not the platform account → admin."""
    leftovers = (
        db.query(User)
        .filter(User.role == "super_admin", User.email != SUPERADMIN_EMAIL)
        .all()
    )
    for u in leftovers:
        u.role = "admin"
        print(f"Migrated legacy super_admin → admin: {u.email}")
    if leftovers:
        db.commit()


def _ensure_tenant_admin(db):
    admin = db.query(User).filter(
        User.email.in_([ADMIN_EMAIL, LEGACY_ADMIN_EMAIL]),
        User.role.in_(["admin", "super_admin"]),
    ).first()

    if admin:
        admin.email = ADMIN_EMAIL
        admin.role = "admin"
        admin.password_hash = hash_password(ADMIN_PASSWORD)
        admin.full_name = admin.full_name or "Tenant Admin"
        admin.is_active = True
        admin.is_verified = True
        db.commit()
        print(f"Updated tenant admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    else:
        admin = User(
            full_name="Tenant Admin",
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"Created tenant admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

    # Ensure a default tenant linked to this admin
    tenant = (
        db.query(Tenant)
        .filter(Tenant.admin_user_id == admin.id)
        .first()
    )
    if not tenant:
        tenant = (
            db.query(Tenant).filter(Tenant.slug == "lalganj").first()
        )
    if not tenant:
        tenant = Tenant(
            name="Lalganj",
            slug="lalganj",
            admin_user_id=admin.id,
            center_latitude=DEFAULT_LAT,
            center_longitude=DEFAULT_LNG,
            center_address=DEFAULT_ADDRESS,
            one_time_fee=Decimal("0"),
            platform_charge_percent=Decimal("5.00"),
            is_active=True,
        )
        db.add(tenant)
        db.flush()
        print("Created default tenant: Lalganj")
    else:
        tenant.admin_user_id = admin.id
        print("Linked existing Lalganj tenant to admin")

    admin.tenant_id = tenant.id

    # Attach orphan restaurants to this tenant
    orphans = db.query(Restaurant).filter(Restaurant.tenant_id.is_(None)).all()
    for r in orphans:
        r.tenant_id = tenant.id
    if orphans:
        print(f"Assigned {len(orphans)} restaurant(s) to Lalganj tenant")

    db.commit()
    return admin, tenant


def seed():
    db = SessionLocal()
    try:
        _ensure_superadmin(db)
        _migrate_legacy_super_admins(db)
        _ensure_tenant_admin(db)
        print("Seed complete.")
        print("  /superadmin  ->  superadmin / superadmin")
        print("  /admin       ->  admin / admin")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
