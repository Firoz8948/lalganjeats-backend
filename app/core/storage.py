# backend/app/core/storage.py
"""Local file storage — swap implementation for S3 in production."""
import uuid
from pathlib import Path

from fastapi import UploadFile, HTTPException

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB


def ensure_upload_dirs() -> None:
    for sub in (
        "restaurants/list_banner",
        "restaurants/menu_banner",
        "home_banners/desktop",
        "home_banners/mobile",
    ):
        (UPLOAD_ROOT / sub).mkdir(parents=True, exist_ok=True)


async def save_upload(
    file: UploadFile,
    folder: str,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    """
    Persist an uploaded image locally.
    Returns a web path like /uploads/restaurants/list_banner/abc.png

    TODO(production): replace body with S3 put_object and return CDN URL.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, or WebP images are allowed.",
        )

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(file.content_type, ".jpg")
    content = await file.read()

    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Image must be {limit_mb} MB or smaller.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    dest_dir = UPLOAD_ROOT / folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = dest_dir / filename
    dest_path.write_bytes(content)

    return f"/uploads/{folder}/{filename}"
