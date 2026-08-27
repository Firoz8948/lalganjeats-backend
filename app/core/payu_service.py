# backend/app/core/payu_service.py
"""PayU India hosted checkout (key + salt SHA-512)."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

PAYU_LIVE_URL = "https://secure.payu.in/_payment"
PAYU_TEST_URL = "https://test.payu.in/_payment"


def payu_configured() -> bool:
    return bool(
        (settings.PAYU_MERCHANT_KEY or "").strip()
        and (settings.PAYU_MERCHANT_SALT or "").strip()
    )


def payu_payment_url() -> str:
    mode = (settings.PAYU_MODE or "test").strip().lower()
    return PAYU_LIVE_URL if mode in ("live", "prod", "production") else PAYU_TEST_URL


def _sha512(text: str) -> str:
    return hashlib.sha512(text.encode("utf-8")).hexdigest()


def payment_hash(
    *,
    key: str,
    txnid: str,
    amount: str,
    productinfo: str,
    firstname: str,
    email: str,
    udf1: str = "",
    udf2: str = "",
    udf3: str = "",
    udf4: str = "",
    udf5: str = "",
    salt: str | None = None,
) -> str:
    """
    Request hash:
    sha512(key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||SALT)
    """
    salt = salt if salt is not None else settings.PAYU_MERCHANT_SALT
    sequence = (
        f"{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|"
        f"{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{salt}"
    )
    return _sha512(sequence)


def response_hash(params: dict[str, Any]) -> str:
    """
    Reverse hash for PayU callback:
    sha512(SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)
    With additional_charges prepended when present.
    """
    salt = settings.PAYU_MERCHANT_SALT
    status = str(params.get("status") or "")
    email = str(params.get("email") or "")
    firstname = str(params.get("firstname") or "")
    productinfo = str(params.get("productinfo") or "")
    amount = str(params.get("amount") or "")
    txnid = str(params.get("txnid") or "")
    key = str(params.get("key") or settings.PAYU_MERCHANT_KEY)
    udf1 = str(params.get("udf1") or "")
    udf2 = str(params.get("udf2") or "")
    udf3 = str(params.get("udf3") or "")
    udf4 = str(params.get("udf4") or "")
    udf5 = str(params.get("udf5") or "")

    base = (
        f"{salt}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|"
        f"{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
    )
    additional = str(params.get("additionalCharges") or params.get("additional_charges") or "")
    if additional:
        base = f"{additional}|{base}"
    return _sha512(base)


def verify_response_hash(params: dict[str, Any]) -> bool:
    received = str(params.get("hash") or "").lower()
    if not received:
        return False
    expected = response_hash(params).lower()
    return expected == received


def format_amount(amount: float) -> str:
    return f"{round(float(amount), 2):.2f}"


def build_checkout_payload(
    *,
    txnid: str,
    amount: float,
    productinfo: str,
    firstname: str,
    email: str,
    phone: str,
    surl: str,
    furl: str,
    udf1: str = "",
    udf2: str = "",
    udf3: str = "",
    udf4: str = "",
    udf5: str = "",
) -> dict[str, str]:
    key = settings.PAYU_MERCHANT_KEY.strip()
    amount_str = format_amount(amount)
    digest = payment_hash(
        key=key,
        txnid=txnid,
        amount=amount_str,
        productinfo=productinfo,
        firstname=firstname or "Customer",
        email=email or "noreply@lalganjeats.com",
        udf1=udf1,
        udf2=udf2,
        udf3=udf3,
        udf4=udf4,
        udf5=udf5,
    )
    return {
        "key": key,
        "txnid": txnid,
        "amount": amount_str,
        "productinfo": productinfo[:100],
        "firstname": (firstname or "Customer")[:60],
        "email": (email or "noreply@lalganjeats.com")[:100],
        "phone": (phone or "")[:20],
        "surl": surl,
        "furl": furl,
        "hash": digest,
        "udf1": udf1,
        "udf2": udf2,
        "udf3": udf3,
        "udf4": udf4,
        "udf5": udf5,
        "service_provider": "payu_paisa",
    }
