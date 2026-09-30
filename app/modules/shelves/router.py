# backend/app/modules/shelves/router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.shelves import service

router = APIRouter(prefix="/api/v1/shelves", tags=["Shelves"])


@router.get("")
def public_shelves(
    category_id: int = Query(..., ge=1),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """Public — curated product rows of a home tab, limited to stores that deliver to the customer."""
    return service.list_public_shelves(db, category_id, lat, lng)
