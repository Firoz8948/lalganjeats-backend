# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import Base, engine
from app.core.storage import ensure_upload_dirs, UPLOAD_ROOT

# ── Import all models (so Base knows them) ─────────────────
from app.modules.superadmin.models import Tenant, DeliveryZone  # noqa: F401 — before User FK
from app.modules.users.models import (
    User, CustomerProfile, Address, CustomerSettings
)
from app.modules.otp.models import OTP
from app.modules.restaurants.models import (
    CatalogCategory, CatalogSubcategory, Restaurant, MenuCategory, MenuItem,
    MenuItemVariant,
)
from app.modules.orders.models import Order, OrderItem, DeliveryProfile, DeliveryOffer
from app.modules.banners.models import HomeBannerSlide
from app.modules.payments.models import (
    PaymentSettings, RestaurantEarning, DeliveryEarning,
    Withdrawal, BankAccount,
)
from app.modules.promocodes.models import PromoCode, PromoCodeUsage  # noqa: F401

# ── Import routers ─────────────────────────────────────────
from app.modules.auth.router        import router as auth_router
from app.modules.superadmin.router  import router as superadmin_router
from app.modules.admin.router       import router as admin_router
from app.modules.banners.router     import router as banners_router
from app.modules.payments.router    import router as payments_router
from app.modules.restaurants.router import router as restaurants_router
from app.modules.hotel_portal.router import router as hotel_portal_router
from app.modules.delivery.router    import router as delivery_router
from app.modules.users.router       import router as users_router
from app.modules.promocodes.router  import (
    public_router as promocodes_public_router,
    admin_router as promocodes_admin_router,
)
from app.modules.getlocation.router import router as getlocation_router
from app.modules.orders.router import router as orders_router
from app.modules.tracking.router import router as tracking_router
from app.modules.websocket.router import router as websocket_router

# ── Create tables ──────────────────────────────────────────
Base.metadata.create_all(bind=engine)
ensure_upload_dirs()

app = FastAPI(title="LalganjEats API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(superadmin_router)
app.include_router(admin_router)
app.include_router(promocodes_admin_router)
app.include_router(promocodes_public_router)
app.include_router(banners_router)
app.include_router(payments_router)
app.include_router(restaurants_router)
app.include_router(hotel_portal_router)
app.include_router(delivery_router)
app.include_router(getlocation_router)
app.include_router(tracking_router)
app.include_router(websocket_router)
app.include_router(users_router)
app.include_router(orders_router)

# Serve uploaded images in local mode (Bunny returns full CDN URLs)
if settings.STORAGE_BACKEND == "local" and UPLOAD_ROOT.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

@app.get("/health")
def health():
    return {"status": "ok", "app": "LalganjEats"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
