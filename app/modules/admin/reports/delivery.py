from email.message import EmailMessage
import smtplib

import httpx
from fastapi import HTTPException

from app.core.config import settings


def send_email_report(
    recipient: str,
    subject: str,
    body: str,
    filename: str,
    pdf_bytes: bytes,
) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise HTTPException(503, "Email delivery is not configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient
    message.set_content(body)
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )
    try:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=30,
        ) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:
        raise HTTPException(502, f"Email delivery failed: {exc}") from exc


def _whatsapp_number(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) < 10:
        raise HTTPException(400, "Recipient WhatsApp number is invalid")
    return digits


def send_whatsapp_report(
    recipient: str,
    caption: str,
    filename: str,
    pdf_bytes: bytes,
) -> None:
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        raise HTTPException(503, "WhatsApp delivery is not configured")
    base_url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_GRAPH_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
    )
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    try:
        with httpx.Client(timeout=30) as client:
            media_response = client.post(
                f"{base_url}/media",
                headers=headers,
                data={"messaging_product": "whatsapp"},
                files={"file": (filename, pdf_bytes, "application/pdf")},
            )
            media_response.raise_for_status()
            media_id = media_response.json()["id"]
            send_response = client.post(
                f"{base_url}/messages",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "to": _whatsapp_number(recipient),
                    "type": "document",
                    "document": {
                        "id": media_id,
                        "filename": filename,
                        "caption": caption,
                    },
                },
            )
            send_response.raise_for_status()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"WhatsApp delivery failed: {exc}") from exc
