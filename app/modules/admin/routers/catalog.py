from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.schemas import CatalogNameCreate, CatalogSubcategoryImageUpdate
from app.modules.admin.services import catalog as catalog_service
from app.modules.users.models import User


router = APIRouter(prefix="/catalog")


def _category_row(item):
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "is_active": item.is_active,
    }


def _subcategory_row(item, product_count: int = 0):
    return {
        "id": item.id,
        "category_id": item.category_id,
        "name": item.name,
        "slug": item.slug,
        "is_active": item.is_active,
        "is_featured": bool(getattr(item, "is_featured", False)),
        "image_url": getattr(item, "image_url", None),
        "product_count": int(product_count or 0),
    }


def _subcategory_row_with_count(db, item, tenant_id: int | None):
    return _subcategory_row(
        item,
        catalog_service.subcategory_product_count(db, item.id, tenant_id),
    )


@router.get("/categories")
def categories(db: Session = Depends(get_db), _=Depends(get_admin)):
    return [_category_row(item) for item in catalog_service.list_categories(db)]


@router.post("/categories", status_code=201)
def create_category(
    payload: CatalogNameCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return _category_row(catalog_service.create_category(db, payload.name))


@router.patch("/categories/{category_id}/toggle")
def toggle_category(
    category_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return _category_row(catalog_service.toggle_category(db, category_id))


@router.get("/subcategories")
def subcategories(
    category_id: int,
    product_sort: Literal["asc", "desc"] | None = Query(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return [
        _subcategory_row(item, product_count)
        for item, product_count in catalog_service.list_subcategories(
            db,
            category_id,
            product_sort,
            tenant_id=current.tenant_id,
        )
    ]


@router.post("/subcategories", status_code=201)
def create_subcategory(
    category_id: int,
    payload: CatalogNameCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    item = catalog_service.create_subcategory(db, category_id, payload.name)
    return _subcategory_row_with_count(db, item, current.tenant_id)


@router.patch("/subcategories/{subcategory_id}/toggle")
def toggle_subcategory(
    subcategory_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    item = catalog_service.toggle_subcategory(db, subcategory_id)
    return _subcategory_row_with_count(db, item, current.tenant_id)


@router.patch("/subcategories/{subcategory_id}/featured")
def toggle_subcategory_featured(
    subcategory_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    item = catalog_service.toggle_subcategory_featured(db, subcategory_id)
    return _subcategory_row_with_count(db, item, current.tenant_id)


@router.patch("/subcategories/{subcategory_id}/image")
def update_subcategory_image(
    subcategory_id: int,
    payload: CatalogSubcategoryImageUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    item = catalog_service.set_subcategory_image(
        db, subcategory_id, payload.image_url
    )
    return _subcategory_row_with_count(db, item, current.tenant_id)
