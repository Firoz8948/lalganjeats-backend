from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.schemas import (
    HomeBannerPatchRequest,
    HomeBannersSaveRequest,
)
from app.modules.banners import service as banner_service

router = APIRouter()


@router.get("/home-banners")
def get_home_banners_admin(
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    slides = banner_service.ensure_slides(db)
    return [banner_service._serialize(slide) for slide in slides]


@router.post("/home-banners", status_code=201)
def create_home_banner(
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    slide = banner_service.create_slide(db)
    return banner_service._serialize(slide)


@router.patch("/home-banners/{slide_id}")
def patch_home_banner(
    slide_id: int,
    body: HomeBannerPatchRequest,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    data = body.model_dump(exclude_unset=True)
    slide = banner_service.update_slide(db, slide_id, **data)
    return banner_service._serialize(slide)


@router.delete("/home-banners/{slide_id}")
def delete_home_banner(
    slide_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    banner_service.delete_slide(db, slide_id)
    return {
        "message": "Slide deleted",
        "slides": [
            banner_service._serialize(slide)
            for slide in banner_service.list_all_slides(db)
        ],
    }


@router.put("/home-banners")
def save_home_banners(
    body: HomeBannersSaveRequest,
    db: Session = Depends(get_db),
    _=Depends(get_admin),
):
    updates = [
        slide.model_dump(exclude_none=False)
        for slide in body.slides
    ]
    slides = banner_service.save_slides(db, updates)
    return [banner_service._serialize(slide) for slide in slides]
