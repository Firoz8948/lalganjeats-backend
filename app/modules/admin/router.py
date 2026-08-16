from fastapi import APIRouter

from app.core.storage import ensure_upload_dirs
from app.modules.admin.routers import (
    banners,
    catalog,
    customers,
    dashboard,
    orders,
    restaurants,
    settlements,
    tenant,
)
from app.modules.admin.reports.router import router as reports_router
from app.modules.delivery_partner.router import router as delivery_partners_router

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

ensure_upload_dirs()

router.include_router(dashboard.router)
router.include_router(catalog.router)
router.include_router(restaurants.router)
router.include_router(banners.router)
router.include_router(customers.router)
router.include_router(orders.router)
router.include_router(settlements.router)
router.include_router(reports_router)
router.include_router(tenant.router)
router.include_router(delivery_partners_router)
