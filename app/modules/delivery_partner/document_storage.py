"""Private delivery-partner document storage.

Unlike public selfies, identity documents are never exposed through /uploads or
the public CDN. Admins retrieve them through an authenticated API endpoint.
"""
import mimetypes
import uuid
from pathlib import Path

import httpx
from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.core.storage import ALLOWED_CONTENT_TYPES


PRIVATE_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "private_uploads"
    / "delivery_partner_docs"
)
MAX_PRIVATE_UPLOAD_BYTES = 5 * 1024 * 1024


def _extension(file: UploadFile, content: bytes) -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Only JPG, PNG, or WebP images are allowed.")
    if not content:
        raise HTTPException(400, "Empty file uploaded.")
    if len(content) > MAX_PRIVATE_UPLOAD_BYTES:
        raise HTTPException(400, "Document image must be 5 MB or smaller.")
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[file.content_type]


async def save_private_document(file: UploadFile, purpose: str) -> str:
    content = await file.read()
    ext = _extension(file, content)
    object_path = f"delivery_partner_docs/{purpose}/{uuid.uuid4().hex}{ext}"

    if settings.STORAGE_BACKEND == "bunny":
        zone = settings.BUNNY_STORAGE_ZONE.strip()
        password = settings.BUNNY_STORAGE_PASSWORD.strip()
        host = settings.BUNNY_STORAGE_HOST.strip().rstrip("/")
        if not zone or not password:
            raise HTTPException(500, "Private Bunny storage is not configured.")
        base = host if host.startswith("http") else f"https://{host}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                f"{base}/{zone}/{object_path}",
                content=content,
                headers={
                    "AccessKey": password,
                    "Content-Type": file.content_type or "application/octet-stream",
                },
            )
        if response.status_code not in (200, 201):
            raise HTTPException(502, "Private document upload failed.")
        return f"bunny:{object_path}"

    relative = object_path.removeprefix("delivery_partner_docs/")
    destination = PRIVATE_ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return f"local:{object_path}"


async def load_private_document(key: str) -> tuple[bytes, str, str]:
    if not key or ":" not in key:
        raise HTTPException(404, "Document not found")
    backend, object_path = key.split(":", 1)
    if not object_path.startswith("delivery_partner_docs/") or ".." in object_path:
        raise HTTPException(400, "Invalid document key")

    if backend == "bunny":
        zone = settings.BUNNY_STORAGE_ZONE.strip()
        password = settings.BUNNY_STORAGE_PASSWORD.strip()
        host = settings.BUNNY_STORAGE_HOST.strip().rstrip("/")
        base = host if host.startswith("http") else f"https://{host}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{base}/{zone}/{object_path}",
                headers={"AccessKey": password},
            )
        if response.status_code != 200:
            raise HTTPException(404, "Document not found")
        content = response.content
    elif backend == "local":
        relative = object_path.removeprefix("delivery_partner_docs/")
        path = PRIVATE_ROOT / relative
        if not path.is_file():
            raise HTTPException(404, "Document not found")
        content = path.read_bytes()
    else:
        raise HTTPException(400, "Invalid document storage backend")

    filename = Path(object_path).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return content, content_type, filename
