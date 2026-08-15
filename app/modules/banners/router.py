# backend/app/modules/banners/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.banners import service as banner_service

router = APIRouter(prefix="/api/v1/banners", tags=["Banners"])


@router.get("")
def get_home_banners(db: Session = Depends(get_db)):
    """Public — active home carousel slides only."""
    slides = banner_service.list_public_slides(db)
    return [banner_service._serialize(s) for s in slides]
