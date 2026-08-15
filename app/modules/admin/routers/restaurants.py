from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.schemas import AdminMenuItemCreate
from app.modules.admin.services import restaurants as admin_restaurant_service
from app.modules.restaurants import service as restaurant_service
from app.modules.restaurants.models import Restaurant
from app.modules.restaurants.schemas import (
    RestaurantCreateRequest,
    RestaurantUpdateRequest,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/restaurants")
def get_all_restaurants(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    query = db.query(Restaurant)
    if current.tenant_id:
        query = query.filter(
            Restaurant.tenant_id == current.tenant_id
        )
    restaurants = query.order_by(Restaurant.created_at.desc()).all()
    return [restaurant_service._admin_row(item) for item in restaurants]


@router.get("/restaurants/{restaurant_id}")
def get_restaurant_admin(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return restaurant_service.get_admin_restaurant(
        db,
        restaurant_id,
        current.tenant_id,
    )


@router.patch("/restaurants/{restaurant_id}")
def update_restaurant_admin(
    restaurant_id: int,
    payload: RestaurantUpdateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return restaurant_service.update_restaurant(
        db,
        restaurant_id,
        payload,
        tenant_id=current.tenant_id,
    )


@router.post("/restaurants", status_code=201)
def create_restaurant(
    payload: RestaurantCreateRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    """Tenant admin adds a restaurant under their tenant."""
    return restaurant_service.create_restaurant(
        db,
        payload,
        tenant_id=current.tenant_id,
    )


@router.post("/upload")
async def upload_restaurant_image(
    request: Request,
    file: UploadFile = File(...),
    purpose: str = Form(...),
    _=Depends(get_admin),
):
    """
    Upload a banner image.
    purpose: list_banner | menu_banner | home_banner_desktop | home_banner_mobile
    Local storage now — replace save_upload with S3 in production.
    """
    return await admin_restaurant_service.upload_restaurant_image(
        request,
        file,
        purpose,
    )


@router.patch("/restaurants/{restaurant_id}/approve")
def approve_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return admin_restaurant_service.approve_restaurant(db, restaurant_id)


@router.get("/restaurants/{restaurant_id}/menu")
def admin_get_restaurant_menu(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    """Admin: list all (non-deleted) menu items for a restaurant."""
    return admin_restaurant_service.get_restaurant_menu(db, restaurant_id)


@router.post("/restaurants/{restaurant_id}/menu", status_code=201)
def admin_add_menu_item(
    restaurant_id: int,
    payload: AdminMenuItemCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    """Admin: add a menu item to a restaurant (impersonation)."""
    return admin_restaurant_service.add_menu_item(
        db,
        restaurant_id,
        payload,
    )


@router.patch("/restaurants/{restaurant_id}/menu/{item_id}")
def admin_toggle_menu_item(
    restaurant_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    """Admin: toggle availability of a menu item."""
    return admin_restaurant_service.toggle_menu_item(
        db,
        restaurant_id,
        item_id,
    )


@router.delete("/restaurants/{restaurant_id}/menu/{item_id}")
def admin_delete_menu_item(
    restaurant_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    """Admin: soft-delete a menu item."""
    return admin_restaurant_service.delete_menu_item(
        db,
        restaurant_id,
        item_id,
    )


@router.patch("/restaurants/{restaurant_id}/banner")
def admin_set_restaurant_banner(
    restaurant_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    """Admin: set banner_url for a restaurant."""
    return admin_restaurant_service.set_restaurant_banner(
        db,
        restaurant_id,
        payload,
    )
