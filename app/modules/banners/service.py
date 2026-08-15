# backend/app/modules/banners/service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.modules.banners.models import HomeBannerSlide


def _serialize(s: HomeBannerSlide) -> dict:
    return {
        "id": s.id,
        "slide_number": s.slide_number,
        "desktop_image_url": s.desktop_image_url,
        "mobile_image_url": s.mobile_image_url,
        "is_active": bool(s.is_active),
    }


def list_all_slides(db: Session) -> list[HomeBannerSlide]:
    return (
        db.query(HomeBannerSlide)
        .order_by(HomeBannerSlide.slide_number)
        .all()
    )


def list_public_slides(db: Session) -> list[HomeBannerSlide]:
    """Active slides only — used on the customer home carousel."""
    return (
        db.query(HomeBannerSlide)
        .filter(HomeBannerSlide.is_active == True)  # noqa: E712
        .order_by(HomeBannerSlide.slide_number)
        .all()
    )


def get_slide(db: Session, slide_id: int) -> HomeBannerSlide:
    slide = db.query(HomeBannerSlide).filter(HomeBannerSlide.id == slide_id).first()
    if not slide:
        raise HTTPException(404, "Banner slide not found")
    return slide


def _next_slide_number(db: Session) -> int:
    row = (
        db.query(HomeBannerSlide.slide_number)
        .order_by(HomeBannerSlide.slide_number.desc())
        .first()
    )
    return (row[0] + 1) if row else 1


def create_slide(db: Session) -> HomeBannerSlide:
    slide = HomeBannerSlide(
        slide_number=_next_slide_number(db),
        is_active=True,
    )
    db.add(slide)
    db.commit()
    db.refresh(slide)
    return slide


def update_slide(db: Session, slide_id: int, **fields) -> HomeBannerSlide:
    slide = get_slide(db, slide_id)
    if "desktop_image_url" in fields:
        slide.desktop_image_url = fields["desktop_image_url"]
    if "mobile_image_url" in fields:
        slide.mobile_image_url = fields["mobile_image_url"]
    if "is_active" in fields and fields["is_active"] is not None:
        slide.is_active = bool(fields["is_active"])
    db.commit()
    db.refresh(slide)
    return slide


def delete_slide(db: Session, slide_id: int) -> None:
    slide = get_slide(db, slide_id)
    db.delete(slide)
    db.commit()
    # Renumber remaining slides 1..n for stable ordering
    remaining = list_all_slides(db)
    for i, s in enumerate(remaining, start=1):
        if s.slide_number != i:
            s.slide_number = i
    db.commit()


def save_slides_bulk(db: Session, updates: list[dict]) -> list[HomeBannerSlide]:
    """Update existing slides by id or slide_number (legacy bulk save)."""
    for item in updates:
        slide = None
        if item.get("id"):
            slide = db.query(HomeBannerSlide).filter(
                HomeBannerSlide.id == item["id"]
            ).first()
        if not slide and item.get("slide_number") is not None:
            slide = db.query(HomeBannerSlide).filter(
                HomeBannerSlide.slide_number == item["slide_number"]
            ).first()
        if not slide:
            continue
        if "desktop_image_url" in item:
            slide.desktop_image_url = item.get("desktop_image_url")
        if "mobile_image_url" in item:
            slide.mobile_image_url = item.get("mobile_image_url")
        if "is_active" in item and item["is_active"] is not None:
            slide.is_active = bool(item["is_active"])
    db.commit()
    return list_all_slides(db)


# Back-compat aliases used by older admin routes
def ensure_slides(db: Session) -> list[HomeBannerSlide]:
    slides = list_all_slides(db)
    if slides:
        return slides
    # Seed three empty slides for first-time setup
    for n in range(1, 4):
        db.add(HomeBannerSlide(slide_number=n, is_active=True))
    db.commit()
    return list_all_slides(db)


def save_slides(db: Session, updates: list[dict]) -> list[HomeBannerSlide]:
    ensure_slides(db)
    return save_slides_bulk(db, updates)
