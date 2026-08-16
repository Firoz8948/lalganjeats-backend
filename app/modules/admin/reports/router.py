from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_admin
from app.modules.admin.reports import delivery, service
from app.modules.admin.reports.models import ReportDelivery
from app.modules.admin.reports.pdf import render_report_pdf, report_filename
from app.modules.admin.reports.schemas import (
    ReportRecipient,
    ReportRequest,
    ReportSendRequest,
    ReportSendResponse,
    ReportSummary,
)
from app.modules.users.models import User


router = APIRouter(prefix="/reports", tags=["Admin Reports"])


@router.get("/recipients", response_model=list[ReportRecipient])
def recipients(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.list_recipients(db, current)


@router.post("/preview", response_model=ReportSummary)
def preview_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    return service.build_report(db, current, payload)


@router.post("/download")
def download_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    summary = service.build_report(db, current, payload)
    filename = report_filename(summary)
    return StreamingResponse(
        BytesIO(render_report_pdf(summary)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/send", response_model=ReportSendResponse)
def send_report(
    payload: ReportSendRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    summary = service.build_report(db, current, payload)
    email, phone = service.get_target_contact(
        db,
        current,
        payload.target_type,
        payload.target_id,
    )
    recipient = payload.recipient or (
        email if payload.channel == "email" else phone
    )
    if not recipient:
        raise HTTPException(
            400,
            f"Selected partner has no {payload.channel} contact",
        )

    audit = ReportDelivery(
        tenant_id=current.tenant_id,
        admin_user_id=current.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        target_name=summary["target_name"],
        period=payload.period,
        period_start=summary["period_start"],
        period_end=summary["period_end"],
        channel=payload.channel,
        recipient=recipient,
        status="pending",
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    filename = report_filename(summary)
    pdf_bytes = render_report_pdf(summary)
    subject = (
        f"LalganjEats {summary['period_label']} report - "
        f"{summary['target_name']}"
    )
    body = (
        f"Hello {summary['target_name']},\n\n"
        f"Attached is your LalganjEats {summary['period_label'].lower()} "
        "aggregate orders, financial and settlement report.\n\n"
        "This report contains no customer or individual order information."
    )
    try:
        if payload.channel == "email":
            delivery.send_email_report(
                recipient,
                subject,
                body,
                filename,
                pdf_bytes,
            )
        else:
            delivery.send_whatsapp_report(
                recipient,
                subject,
                filename,
                pdf_bytes,
            )
    except HTTPException as exc:
        audit.status = "failed"
        audit.error_message = str(exc.detail)[:1000]
        db.commit()
        raise

    audit.status = "sent"
    audit.sent_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "ok": True,
        "channel": payload.channel,
        "recipient": recipient,
        "delivery_id": audit.id,
        "message": f"Report sent by {payload.channel}",
    }


@router.get("/history")
def report_history(
    db: Session = Depends(get_db),
    current: User = Depends(get_admin),
):
    rows = (
        db.query(ReportDelivery)
        .filter(ReportDelivery.tenant_id == current.tenant_id)
        .order_by(ReportDelivery.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": row.id,
            "target_type": row.target_type,
            "target_name": row.target_name,
            "period": row.period,
            "channel": row.channel,
            "recipient": row.recipient,
            "status": row.status,
            "error_message": row.error_message,
            "created_at": row.created_at,
            "sent_at": row.sent_at,
        }
        for row in rows
    ]
