# backend/app/modules/app_updates/schemas.py
from pydantic import BaseModel
from typing import Optional


class AppUpdateManifestOut(BaseModel):
    update_available: bool
    version: Optional[str] = None
    bundle_url: Optional[str] = None
    checksum: Optional[str] = None
    release_notes: Optional[str] = None
    is_mandatory: bool = False
