"""Renflair SMS gateway for non-OTP messages (V3 / V4). OTP SMS is in app.modules.otp."""
from __future__ import annotations

import logging
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE = "https://sms.renflair.in"


def _get(path: str, params: dict) -> dict:
    api = (settings.RENFLAIR_API_KEY or "").strip()
    if not api:
        logger.warning("RENFLAIR_API_KEY missing — SMS skipped: %s %s", path, params)
        return {"ok": False, "skipped": True, "reason": "no_api_key"}

    qs = urlencode({**params, "API": api})
    url = f"{BASE}/{path}?{qs}"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        logger.info("Renflair %s → %s", path, body[:200])
        return {"ok": True, "raw": body}
    except Exception as exc:
        logger.exception("Renflair SMS failed (%s): %s", path, exc)
        return {"ok": False, "error": str(exc)}


ADMIN_ORDER_ALERT_PHONES = ("9670517135", "9721054930")


def send_order_with_customer(phone: str, order_id, customer_name: str) -> dict:
    """V3 — customer order confirmation (name + order id)."""
    phone = "".join(c for c in str(phone) if c.isdigit())[-10:]
    cname = "".join(ch for ch in str(customer_name or "Customer") if ch.isalnum() or ch in " .")[:30].strip() or "Customer"
    return _get(
        "V3.php",
        {"PHONE": phone, "OID": str(order_id), "CNAME": cname},
    )


def send_order_alert(phone: str, order_id) -> dict:
    """V4 — order id alert (hotel / admin / DP assigned)."""
    phone = "".join(c for c in str(phone) if c.isdigit())[-10:]
    return _get("V4.php", {"PHONE": phone, "OID": str(order_id)})


def notify_new_order(
    *,
    order_number: str,
    customer_phone: str | None,
    customer_name: str | None,
    hotel_phone: str | None,
) -> None:
    """Fan-out SMS when a new order is actually placed (COD) or prepaid is paid."""
    if customer_phone:
        try:
            send_order_with_customer(customer_phone, order_number, customer_name or "Customer")
        except Exception:
            logger.exception("Customer order SMS failed (order=%s)", order_number)
    if hotel_phone:
        try:
            send_order_alert(hotel_phone, order_number)
        except Exception:
            logger.exception("Hotel SMS alert failed (order=%s)", order_number)
    for admin_phone in ADMIN_ORDER_ALERT_PHONES:
        try:
            send_order_alert(admin_phone, order_number)
        except Exception:
            logger.exception(
                "Admin SMS alert failed (phone=%s, order=%s)",
                admin_phone, order_number,
            )
