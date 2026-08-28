# backend/app/modules/app_updates/service.py
from sqlalchemy.orm import Session
from app.modules.app_updates.models import AppUpdateRelease
from app.modules.app_updates.schemas import AppUpdateManifestOut


def get_latest_manifest(db: Session, app_id: str, current_version: str = "1.0.0") -> AppUpdateManifestOut:
    release = db.query(AppUpdateRelease).filter(
        AppUpdateRelease.app_id == app_id.strip(),
        AppUpdateRelease.is_active == True
    ).order_by(AppUpdateRelease.id.desc()).first()

    if not release or release.version == current_version.strip():
        return AppUpdateManifestOut(update_available=False)

    return AppUpdateManifestOut(
        update_available=True,
        version=release.version,
        bundle_url=release.bundle_url,
        checksum=release.checksum,
        release_notes=release.release_notes,
        is_mandatory=release.is_mandatory,
    )
