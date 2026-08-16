from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.core.storage import save_upload
from app.modules.delivery_partner import document_storage, service
from app.modules.delivery_partner.schemas import (
    DOCUMENT_TYPES,
    UPLOAD_TYPES,
    DeliveryPartnerCreate,
    DeliveryPartnerOut,
    DeliveryPartnerStatusUpdate,
    UploadResult,
)
from app.modules.users.models import User


router = APIRouter(prefix="/delivery-partners", tags=["Admin Delivery Partners"])


@router.get("", response_model=list[DeliveryPartnerOut])
def list_delivery_partners(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.list_delivery_partners(db, current.tenant_id)


@router.post("", response_model=DeliveryPartnerOut, status_code=201)
def create_delivery_partner(
    payload: DeliveryPartnerCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.create_delivery_partner(db, current.tenant_id, payload)


@router.patch("/{partner_id}/status")
def update_delivery_partner_status(
    partner_id: int,
    payload: DeliveryPartnerStatusUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.set_delivery_partner_status(
        db,
        current.tenant_id,
        partner_id,
        payload.is_active,
    )


@router.post("/upload", response_model=UploadResult)
async def upload_delivery_partner_image(
    purpose: str = Form(...),
    file: UploadFile = File(...),
    _: User = Depends(get_admin),
):
    if purpose not in UPLOAD_TYPES:
        raise HTTPException(400, f"purpose must be one of: {', '.join(UPLOAD_TYPES)}")
    if purpose == "selfie":
        url = await save_upload(file, "delivery_partners/selfies")
        return UploadResult(purpose=purpose, url=url)
    key = await document_storage.save_private_document(file, purpose)
    return UploadResult(purpose=purpose, document_key=key)


@router.get("/{partner_id}/documents/{purpose}")
async def download_delivery_partner_document(
    partner_id: int,
    purpose: str,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    if purpose not in DOCUMENT_TYPES:
        raise HTTPException(404, "Unknown document type")
    key = service.get_document_key(
        db,
        current.tenant_id,
        partner_id,
        purpose,
    )
    content, content_type, filename = await document_storage.load_private_document(key)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
