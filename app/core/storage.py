# backend/app/core/storage.py
"""File storage — local disk (dev) or Bunny CDN (production)."""
import uuid
from pathlib import Path

import httpx
from fastapi import UploadFile, HTTPException

from app.core.config import settings

UPLOAD_ROOT = Path(__file__).resolve().parent.parent.parent / "uploads"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB


def ensure_upload_dirs() -> None:
    if settings.STORAGE_BACKEND != "local":
        return
    for sub in (
        "restaurants/list_banner",
        "restaurants/menu_banner",
        "home_banners/desktop",
        "home_banners/mobile",
    ):
        (UPLOAD_ROOT / sub).mkdir(parents=True, exist_ok=True)


def _validate_and_read(
    file: UploadFile,
    content: bytes,
    max_bytes: int,
) -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, or WebP images are allowed.",
        )
    if len(content) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"Image must be {limit_mb} MB or smaller.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    return ext_map.get(file.content_type, ".jpg")


async def _save_local(folder: str, filename: str, content: bytes) -> str:
    dest_dir = UPLOAD_ROOT / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / filename).write_bytes(content)
    return f"/uploads/{folder}/{filename}"


async def _save_bunny(
    folder: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    zone = settings.BUNNY_STORAGE_ZONE.strip()
    password = settings.BUNNY_STORAGE_PASSWORD.strip()
    host = settings.BUNNY_STORAGE_HOST.strip().rstrip("/")
    cdn = settings.BUNNY_CDN_URL.strip().rstrip("/")

    if not zone or not password or not cdn:
        raise HTTPException(
            status_code=500,
            detail="Bunny storage is not configured (zone/password/CDN URL).",
        )

    # host may be "sg.storage.bunnycdn.com" or full URL
    if host.startswith("http"):
        base = host.rstrip("/")
    else:
        base = f"https://{host}"

    object_path = f"{folder}/{filename}".replace("\\", "/")
    upload_url = f"{base}/{zone}/{object_path}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.put(
            upload_url,
            content=content,
            headers={
                "AccessKey": password,
                "Content-Type": content_type or "application/octet-stream",
            },
        )

    if response.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Bunny upload failed ({response.status_code}).",
        )

    return f"{cdn}/{object_path}"


async def save_upload(
    file: UploadFile,
    folder: str,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    """
    Persist an uploaded image.
    Returns:
      - local:  /uploads/...
      - bunny:  https://lalganjeats-cdn.b-cdn.net/...
    """
    content = await file.read()
    ext = _validate_and_read(file, content, max_bytes)
    filename = f"{uuid.uuid4().hex}{ext}"
    folder = folder.strip("/").replace("\\", "/")

    if settings.STORAGE_BACKEND == "bunny":
        return await _save_bunny(
            folder,
            filename,
            content,
            file.content_type or "application/octet-stream",
        )

    return await _save_local(folder, filename, content)
