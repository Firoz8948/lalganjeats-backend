import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.modules.users.models import User
from app.modules.app_updates.schemas import AppUpdateManifestOut
from app.modules.app_updates.models import AppUpdateRelease
from app.modules.app_updates import service
from app.core.storage import _save_local, _save_bunny
from app.core.config import settings

router = APIRouter(prefix="/api/v1/app-updates", tags=["App Live Updates"])


@router.get("/manifest", response_model=AppUpdateManifestOut)
def get_manifest(
    app_id: str = Query(..., description="customer | hotel_partner | delivery_partner"),
    version: str = Query("1.0.0", description="Current app version"),
    db: Session = Depends(get_db),
):
    return service.get_latest_manifest(db, app_id, version)


@router.post("/publish")
async def publish_update(
    app_id: str = Form(...),
    version: str = Form(...),
    release_notes: str = Form(""),
    is_mandatory: bool = Form(False),
    bundle_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
):
    authorized = False
    if x_admin_key and (x_admin_key == settings.SECRET_KEY or (settings.BUNNY_STORAGE_PASSWORD and x_admin_key == settings.BUNNY_STORAGE_PASSWORD)):
        authorized = True
    elif credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("role") in ("admin", "super_admin"):
                authorized = True
        except Exception:
            pass

    if not authorized:
        raise HTTPException(403, "Admin authorization required to publish live updates")
    content = await bundle_file.read()
    if len(content) == 0:
        raise HTTPException(400, "Empty bundle file uploaded")

    checksum = hashlib.sha256(content).hexdigest()
    filename = f"{app_id}-v{version}-{checksum[:8]}.zip"

    if settings.STORAGE_BACKEND == "bunny" and settings.BUNNY_STORAGE_ZONE:
        bundle_url = await _save_bunny(f"ota/{app_id}", filename, content, "application/zip")
    else:
        bundle_url = await _save_local(f"ota/{app_id}", filename, content)

    # Deactivate previous active releases for this app
    db.query(AppUpdateRelease).filter(AppUpdateRelease.app_id == app_id).update({"is_active": False})

    release = AppUpdateRelease(
        app_id=app_id,
        version=version,
        bundle_url=bundle_url,
        checksum=checksum,
        release_notes=release_notes,
        is_mandatory=is_mandatory,
        is_active=True,
    )
    db.add(release)
    db.commit()
    db.refresh(release)

    return {
        "status": "published",
        "app_id": app_id,
        "version": version,
        "bundle_url": bundle_url,
        "checksum": checksum,
    }
