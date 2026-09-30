from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.shelves import service as shelf_service
from app.modules.shelves.schemas import ShelfSave
from app.modules.users.models import User

router = APIRouter(prefix="/shelves")


@router.get("")
def list_shelves(
    category_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    return shelf_service.list_admin_shelves(db, shelf_service.require_category(db, category_id))


@router.get("/products")
def search_products(
    category_id: int = Query(..., ge=1),
    q: str = Query("", max_length=80),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return shelf_service.search_admin_products(db, category_id, q, current.tenant_id)


@router.post("", status_code=201)
def create_shelf(
    payload: ShelfSave,
    category_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return shelf_service.create_shelf(db, category_id, payload, current.tenant_id)


@router.put("/{shelf_id}")
def update_shelf(
    shelf_id: int,
    payload: ShelfSave,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return shelf_service.update_shelf(db, shelf_id, payload, current.tenant_id)


@router.delete("/{shelf_id}", status_code=204)
def delete_shelf(
    shelf_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    shelf_service.delete_shelf(db, shelf_id)
