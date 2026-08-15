# backend/app/modules/otp/gateway.py
"""Renflair V1 — OTP SMS only."""
from __future__ import annotations

import logging
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE = "https://sms.renflair.in"


def send_otp_sms(phone: str, otp: str) -> dict:
    """Send OTP via Renflair V1.php."""
    api = (settings.RENFLAIR_API_KEY or "").strip()
    phone_digits = "".join(c for c in str(phone) if c.isdigit())[-10:]
    if not api:
        logger.warning("RENFLAIR_API_KEY missing — OTP SMS skipped for %s", phone_digits)
        return {"ok": False, "skipped": True, "reason": "no_api_key"}

    qs = urlencode({"API": api, "PHONE": phone_digits, "OTP": str(otp)})
    url = f"{BASE}/V1.php?{qs}"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        logger.info("Renflair V1 OTP → %s", body[:200])
        return {"ok": True, "raw": body}
    except Exception as exc:
        logger.exception("Renflair OTP SMS failed: %s", exc)
        return {"ok": False, "error": str(exc)}
