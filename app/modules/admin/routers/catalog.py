from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.schemas import CatalogNameCreate
from app.modules.admin.services import catalog as catalog_service


router = APIRouter(prefix="/catalog")


def _category_row(item):
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "is_active": item.is_active,
    }


def _subcategory_row(item):
    return {
        "id": item.id,
        "category_id": item.category_id,
        "name": item.name,
        "slug": item.slug,
        "is_active": item.is_active,
    }


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
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return [
        _subcategory_row(item)
        for item in catalog_service.list_subcategories(db, category_id)
    ]


@router.post("/subcategories", status_code=201)
def create_subcategory(
    category_id: int,
    payload: CatalogNameCreate,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return _subcategory_row(
        catalog_service.create_subcategory(db, category_id, payload.name)
    )


@router.patch("/subcategories/{subcategory_id}/toggle")
def toggle_subcategory(
    subcategory_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return _subcategory_row(
        catalog_service.toggle_subcategory(db, subcategory_id)
    )
